import pandas as pd
import pytest

from src.engine.trader.config import load_universe_config
from src.exchange.data.market_data import MarketTicker
from src.universe.selection import select_symbols_for_backfill


class FakeMarketData:
    def __init__(self):
        self.ohlcv_calls = []

    async def fetch_market_tickers(self):
        return [
            MarketTicker(symbol="KEEP/USDT:USDT", quote_volume=10_000_000),
            MarketTicker(symbol="THIN/USDT:USDT", quote_volume=4_999_999),
            MarketTicker(symbol="LOW_DAILY/USDT:USDT", quote_volume=20_000_000),
            MarketTicker(symbol="ALSO_LIQUID/USDT:USDT", quote_volume=30_000_000),
        ]

    async def fetch_ohlcv(
        self,
        symbol,
        timeframe,
        limit,
        *,
        since=None,
        end_ts=None,
    ):
        self.ohlcv_calls.append((symbol, timeframe, limit, since, end_ts))
        volumes = {
            "KEEP/USDT:USDT": [600_000, 600_000, 600_000],
            "LOW_DAILY/USDT:USDT": [100_000, 100_000, 100_000],
            "ALSO_LIQUID/USDT:USDT": [600_000, 600_000, 600_000],
        }[symbol]
        return pd.DataFrame(
            {
                "timestamp": [1, 2, 3],
                "open": [10, 10, 10],
                "high": [10, 10, 10],
                "low": [10, 10, 10],
                "close": [10, 10, 10],
                "volume": volumes,
            }
        )


async def _no_sleep(_seconds):
    return None


@pytest.mark.asyncio
async def test_select_symbols_for_backfill_applies_ticker_and_prefilter_ohlcv():
    universe_cfg = load_universe_config("configs/universe/dev.yml")
    fake = FakeMarketData()

    result = await select_symbols_for_backfill(
        market_data=fake,
        universe_cfg=universe_cfg,
        prefilter_end_ts=10_000,
        prefilter_pause_seconds=0,
        sleep=_no_sleep,
    )

    assert result.ticker_count == 4
    assert result.after_ticker_liquidity_count == 3
    assert result.symbols == ["KEEP/USDT:USDT", "ALSO_LIQUID/USDT:USDT"]
    assert [call[0] for call in fake.ohlcv_calls] == [
        "KEEP/USDT:USDT",
        "LOW_DAILY/USDT:USDT",
        "ALSO_LIQUID/USDT:USDT",
    ]
    assert all(call[1] == "1d" for call in fake.ohlcv_calls)
