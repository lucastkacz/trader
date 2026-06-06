import pandas as pd
import pytest

from src.data.ohlcv import OHLCVRetentionPolicy
from src.data.storage.local_parquet import LocalOHLCVParquetStore
from src.data.sync import (
    OHLCVBackfillRequest,
    OHLCVBackfillService,
    OHLCVFetchPolicy,
    OHLCVRefreshRequest,
    OHLCVRefreshService,
)


class FakeMarketDataAdapter:
    def __init__(self, rows_by_symbol: dict[str, list[list[float]]]):
        self.rows_by_symbol = rows_by_symbol
        self.universe_calls = 0

    async def fetch_universe(self, min_volume: float) -> list[str]:
        self.universe_calls += 1
        return list(self.rows_by_symbol)

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        *,
        since: int | None = None,
        end_ts: int | None = None,
    ) -> pd.DataFrame:
        rows = self.rows_by_symbol[symbol]
        selected = [
            row
            for row in rows
            if (since is None or row[0] >= since)
            and (end_ts is None or row[0] <= end_ts)
        ][:limit]
        return pd.DataFrame(
            selected,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )


class FailingSymbolMarketDataAdapter(FakeMarketDataAdapter):
    def __init__(
        self,
        rows_by_symbol: dict[str, list[list[float]]],
        failing_symbol: str,
    ):
        super().__init__(rows_by_symbol)
        self.failing_symbol = failing_symbol

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        *,
        since: int | None = None,
        end_ts: int | None = None,
    ) -> pd.DataFrame:
        if symbol == self.failing_symbol:
            raise RuntimeError("temporary exchange failure")
        return await super().fetch_ohlcv(
            symbol,
            timeframe,
            limit,
            since=since,
            end_ts=end_ts,
        )


async def _no_sleep(_seconds: float) -> None:
    return None


def _policy() -> OHLCVFetchPolicy:
    return OHLCVFetchPolicy(
        fetch_limit=2,
        max_retries=0,
        retry_backoff_seconds=0,
        request_pause_seconds=0,
    )


@pytest.mark.asyncio
async def test_ohlcv_backfill_service_fetches_paginates_and_persists(tmp_path):
    rows = {
        "BTC/USDT:USDT": [
            [1600000000000, 10.0, 11.0, 9.0, 10.5, 100.0],
            [1600000060000, 11.0, 12.0, 10.0, 11.5, 110.0],
            [1600000120000, 12.0, 13.0, 11.0, 12.5, 120.0],
        ],
    }
    store = LocalOHLCVParquetStore(str(tmp_path))
    service = OHLCVBackfillService(
        market_data=FakeMarketDataAdapter(rows),
        store=store,
        policy=_policy(),
        sleep=_no_sleep,
    )

    result = await service.run(
        OHLCVBackfillRequest(
            exchange_id="bybit",
            timeframe="1m",
            start_ts=1600000000000,
            end_ts=1600000120000,
            min_volume=1_000_000,
        )
    )

    loaded = store.load_ohlcv("BTC/USDT:USDT", "1m", "bybit")
    metadata = store.read_ohlcv_metadata("BTC/USDT:USDT", "1m", "bybit")
    assert result.success_count == 1
    assert loaded["timestamp"].tolist() == [
        1600000000000,
        1600000060000,
        1600000120000,
    ]
    assert metadata is not None
    assert metadata.status == "COMPLETE"
    assert metadata.total_candles == 3


@pytest.mark.asyncio
async def test_ohlcv_refresh_service_fetches_missing_tail_and_applies_retention(tmp_path):
    rows = {
        "ETH/USDT:USDT": [
            [1600000000000, 10.0, 11.0, 9.0, 10.5, 100.0],
            [1600000060000, 11.0, 12.0, 10.0, 11.5, 110.0],
            [1600000120000, 12.0, 13.0, 11.0, 12.5, 120.0],
        ],
    }
    store = LocalOHLCVParquetStore(str(tmp_path))
    store.save_ohlcv(
        "ETH/USDT:USDT",
        "1m",
        pd.DataFrame(
            rows["ETH/USDT:USDT"][:2],
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        ),
        {"status": "COMPLETE", "source": "bybit"},
        exchange="bybit",
    )
    service = OHLCVRefreshService(
        market_data=FakeMarketDataAdapter(rows),
        store=store,
        policy=_policy(),
        sleep=_no_sleep,
    )

    result = await service.run(
        OHLCVRefreshRequest(
            exchange_id="bybit",
            timeframe="1m",
            symbols=["ETH/USDT:USDT"],
            end_ts=1600000120000,
            overlap_bars=1,
            missing_lookback_bars=3,
            retention_policy=OHLCVRetentionPolicy(max_bars=2),
        )
    )

    loaded = store.load_ohlcv("ETH/USDT:USDT", "1m", "bybit")
    metadata = store.read_ohlcv_metadata("ETH/USDT:USDT", "1m", "bybit")
    assert result.results[0].status == "COMPLETE"
    assert loaded["timestamp"].tolist() == [1600000060000, 1600000120000]
    assert metadata is not None
    assert metadata.total_candles == 2


@pytest.mark.asyncio
async def test_ohlcv_refresh_service_records_symbol_failure_and_continues(tmp_path):
    rows = {
        "GOOD/USDT:USDT": [
            [1600000000000, 10.0, 11.0, 9.0, 10.5, 100.0],
            [1600000060000, 11.0, 12.0, 10.0, 11.5, 110.0],
        ],
        "BAD/USDT:USDT": [
            [1600000000000, 20.0, 21.0, 19.0, 20.5, 200.0],
        ],
    }
    store = LocalOHLCVParquetStore(str(tmp_path))
    service = OHLCVRefreshService(
        market_data=FailingSymbolMarketDataAdapter(rows, "BAD/USDT:USDT"),
        store=store,
        policy=_policy(),
        sleep=_no_sleep,
    )

    result = await service.run(
        OHLCVRefreshRequest(
            exchange_id="bybit",
            timeframe="1m",
            symbols=["BAD/USDT:USDT", "GOOD/USDT:USDT"],
            end_ts=1600000060000,
            overlap_bars=0,
            missing_lookback_bars=2,
        )
    )

    statuses = {item.symbol: item.status for item in result.results}
    loaded = store.load_ohlcv("GOOD/USDT:USDT", "1m", "bybit")
    assert statuses == {
        "BAD/USDT:USDT": "FAILED",
        "GOOD/USDT:USDT": "COMPLETE",
    }
    assert result.success_count == 1
    assert result.failure_count == 1
    assert loaded["timestamp"].tolist() == [1600000000000, 1600000060000]
