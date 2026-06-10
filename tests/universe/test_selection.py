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
            MarketTicker(symbol="LOW_INTRADAY/USDT:USDT", quote_volume=20_000_000),
            MarketTicker(symbol="MEGA/USDT:USDT", quote_volume=30_000_000),
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
        quote_volume = _quote_volume_for(symbol, timeframe)
        close = 10.0
        volume = quote_volume / close
        return pd.DataFrame(
            {
                "timestamp": [1, 2, 3],
                "open": [close, close, close],
                "high": [close, close, close],
                "low": [close, close, close],
                "close": [close, close, close],
                "volume": [volume, volume, volume],
            }
        )


async def _no_sleep(_seconds):
    return None


@pytest.mark.asyncio
async def test_select_symbols_for_backfill_applies_pre_download_filters():
    universe_cfg = _test_universe_config()
    fake = FakeMarketData()

    result = await select_symbols_for_backfill(
        market_data=fake,
        universe_cfg=universe_cfg,
        pre_download_end_ts_by_timeframe={"1d": 10_000, "1m": 20_000},
        prefilter_pause_seconds=0,
        sleep=_no_sleep,
    )

    assert result.ticker_count == 6
    assert result.after_ticker_liquidity_count == 5
    assert result.after_daily_liquidity_count == 4
    assert result.after_intraday_liquidity_count == 3
    assert result.after_mega_caps_count == 2
    assert result.symbols == ["KEEP/USDT:USDT", "ALSO_LIQUID/USDT:USDT"]
    assert [call[1] for call in fake.ohlcv_calls].count("1d") == 5
    assert [call[1] for call in fake.ohlcv_calls].count("1m") == 4


def _quote_volume_for(symbol: str, timeframe: str) -> float:
    if timeframe == "1d":
        return {
            "KEEP/USDT:USDT": 10_000_000,
            "LOW_DAILY/USDT:USDT": 1_000_000,
            "LOW_INTRADAY/USDT:USDT": 10_000_000,
            "MEGA/USDT:USDT": 10_000_000,
            "ALSO_LIQUID/USDT:USDT": 10_000_000,
        }[symbol]
    return {
        "KEEP/USDT:USDT": 10_000,
        "LOW_INTRADAY/USDT:USDT": 1_000,
        "MEGA/USDT:USDT": 100_000,
        "ALSO_LIQUID/USDT:USDT": 20_000,
    }[symbol]


def _test_universe_config():
    universe_cfg = load_universe_config("configs/universe/dev.yml")
    pre_download = universe_cfg.filters.pre_download
    return universe_cfg.model_copy(
        update={
            "filters": universe_cfg.filters.model_copy(
                update={
                    "pre_download": pre_download.model_copy(
                        update={
                            "mega_caps": pre_download.mega_caps.model_copy(
                                update={"exclude_top_n": 1}
                            )
                        }
                    )
                }
            )
        }
    )
