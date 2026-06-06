from datetime import datetime, timezone
import json

import pandas as pd
import pytest

from src.data.storage.local_parquet import LocalOHLCVParquetStore
from src.engine.trader.runtime.pair_validity.refresh import (
    PairDataRefreshPolicy,
    refresh_promoted_pair_market_data,
    refresh_symbol_market_data,
)
from src.engine.trader.runtime.artifacts import build_pair_artifact


@pytest.mark.asyncio
async def test_refresh_symbol_refetches_overlap_and_appends_closed_candles(tmp_path):
    storage = LocalOHLCVParquetStore(str(tmp_path / "parquet"))
    storage.save_ohlcv(
        "AAA/USDT",
        "1m",
        _ohlcv("2026-05-18T00:00:00Z", periods=10),
        {"status": "COMPLETE", "first_ts": str(_ms("2026-05-18T00:00:00Z"))},
        exchange="bybit",
    )
    calls = []

    async def fake_fetch_klines(**kwargs):
        calls.append(kwargs)
        assert kwargs["since"] == _ms("2026-05-18T00:07:00Z")
        assert kwargs["end_ts"] == _ms("2026-05-18T00:14:00Z")
        return _ohlcv("2026-05-18T00:07:00Z", periods=8)

    result = await refresh_symbol_market_data(
        storage=storage,
        exchange=object(),
        exchange_id="bybit",
        symbol="AAA/USDT",
        timeframe="1m",
        policy=PairDataRefreshPolicy(
            overlap_bars=2,
            missing_lookback_bars=100,
            fetch_limit=1000,
        ),
        fetch_klines=fake_fetch_klines,
        end_ms=_ms("2026-05-18T00:14:00Z"),
    )

    refreshed = storage.load_ohlcv("AAA/USDT", "1m", exchange="bybit")
    assert result.status == "REFRESHED"
    assert result.before_latest_at == "2026-05-18T00:09:00+00:00"
    assert result.after_latest_at == "2026-05-18T00:14:00+00:00"
    assert result.fetched_bars == 8
    assert len(refreshed) == 15
    assert int(refreshed["timestamp"].max()) == _ms("2026-05-18T00:14:00Z")
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_refresh_promoted_pair_data_fetches_unique_artifact_symbols(tmp_path):
    artifact_path = tmp_path / "surviving_pairs.json"
    artifact_path.write_text(
        json.dumps(
            build_pair_artifact(
                [
                    _pair("AAA/USDT", "BBB/USDT"),
                    _pair("AAA/USDT", "CCC/USDT"),
                ],
                timeframe="1m",
                exchange="bybit",
                generated_at="2026-05-18T00:00:00+00:00",
            )
        ),
        encoding="utf-8",
    )
    storage = LocalOHLCVParquetStore(str(tmp_path / "parquet"))
    seen = []

    async def fake_fetch_klines(**kwargs):
        seen.append(kwargs["symbol"])
        return _ohlcv("2026-05-18T00:00:00Z", periods=3)

    report = await refresh_promoted_pair_market_data(
        surviving_pairs_path=artifact_path,
        storage=storage,
        exchange=object(),
        exchange_id="bybit",
        timeframe="1m",
        policy=PairDataRefreshPolicy(
            overlap_bars=1,
            missing_lookback_bars=3,
            fetch_limit=1000,
        ),
        fetch_klines=fake_fetch_klines,
        now=datetime(2026, 5, 18, 0, 3, tzinfo=timezone.utc),
    )

    assert seen == ["AAA/USDT", "BBB/USDT", "CCC/USDT"]
    assert report.symbol_count == 3
    assert {result.status for result in report.results} == {"REFRESHED"}


@pytest.mark.asyncio
async def test_refresh_symbol_continues_after_partial_page_before_closed_candle_end(tmp_path):
    storage = LocalOHLCVParquetStore(str(tmp_path / "parquet"))
    calls = []
    pages = [
        _ohlcv("2026-05-18T00:00:00Z", periods=3),
        _ohlcv("2026-05-18T00:03:00Z", periods=2),
        _ohlcv("2026-05-18T00:05:00Z", periods=2),
    ]

    async def fake_fetch_klines(**kwargs):
        calls.append(kwargs)
        return pages[len(calls) - 1]

    result = await refresh_symbol_market_data(
        storage=storage,
        exchange=object(),
        exchange_id="bybit",
        symbol="AAA/USDT",
        timeframe="1m",
        policy=PairDataRefreshPolicy(
            overlap_bars=0,
            missing_lookback_bars=7,
            fetch_limit=3,
        ),
        fetch_klines=fake_fetch_klines,
        end_ms=_ms("2026-05-18T00:06:00Z"),
    )

    assert result.status == "REFRESHED"
    assert result.after_latest_at == "2026-05-18T00:06:00+00:00"
    assert result.fetched_bars == 7
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_refresh_symbol_labels_incomplete_window_honestly(tmp_path):
    storage = LocalOHLCVParquetStore(str(tmp_path / "parquet"))
    pages = [
        _ohlcv("2026-05-18T00:00:00Z", periods=2),
        pd.DataFrame(),
    ]

    async def fake_fetch_klines(**kwargs):
        return pages.pop(0)

    result = await refresh_symbol_market_data(
        storage=storage,
        exchange=object(),
        exchange_id="bybit",
        symbol="AAA/USDT",
        timeframe="1m",
        policy=PairDataRefreshPolicy(
            overlap_bars=0,
            missing_lookback_bars=5,
            fetch_limit=3,
        ),
        fetch_klines=fake_fetch_klines,
        end_ms=_ms("2026-05-18T00:04:00Z"),
    )

    metadata = storage.read_metadata("AAA/USDT", "1m", exchange="bybit")
    assert result.status == "INCOMPLETE"
    assert result.notes == ["local_data_older_than_closed_candle_end"]
    assert metadata["refresh_status"] == "INCOMPLETE"


def test_pair_data_refresh_policy_rejects_invalid_values():
    with pytest.raises(ValueError, match="overlap_bars"):
        PairDataRefreshPolicy(overlap_bars=-1, missing_lookback_bars=10, fetch_limit=100)
    with pytest.raises(ValueError, match="missing_lookback_bars"):
        PairDataRefreshPolicy(overlap_bars=1, missing_lookback_bars=0, fetch_limit=100)
    with pytest.raises(ValueError, match="fetch_limit"):
        PairDataRefreshPolicy(overlap_bars=1, missing_lookback_bars=10, fetch_limit=0)


def _pair(asset_x: str, asset_y: str) -> dict:
    return {
        "Asset_X": asset_x,
        "Asset_Y": asset_y,
        "P_Value": 0.03,
        "Hedge_Ratio": 1.2,
        "Half_Life": 40.0,
        "Best_Params": {"lookback_bars": 60, "entry_z": 1.5},
        "Performance": {"sharpe_ratio": 1.2, "final_pnl_pct": 0.03},
    }


def _ohlcv(start: str, periods: int) -> pd.DataFrame:
    timestamp = pd.date_range(start, periods=periods, freq="1min")
    return pd.DataFrame(
        {
            "timestamp": [int(ts.timestamp() * 1000) for ts in timestamp],
            "open": [100.0 + index for index in range(periods)],
            "high": [101.0 + index for index in range(periods)],
            "low": [99.0 + index for index in range(periods)],
            "close": [100.5 + index for index in range(periods)],
            "volume": [1000.0] * periods,
        }
    )


def _ms(value: str) -> int:
    return int(pd.Timestamp(value).timestamp() * 1000)
