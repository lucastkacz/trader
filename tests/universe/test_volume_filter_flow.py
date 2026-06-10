import pandas as pd
import pytest

from src.engine.trader.config import load_universe_config
from src.exchange.data.market_data import MarketTicker
from src.universe.selection import select_symbols_for_backfill


class ControlledVolumeMarketData:
    """Fake exchange data where each symbol is designed to fail at one stage."""

    async def fetch_market_tickers(self) -> list[MarketTicker]:
        return [
            MarketTicker(symbol="FINAL/USDT:USDT", quote_volume=50_000_000),
            MarketTicker(symbol="MEGA/USDT:USDT", quote_volume=50_000_000),
            MarketTicker(symbol="INTRADAY_LOW/USDT:USDT", quote_volume=50_000_000),
            MarketTicker(symbol="DAILY_LOW/USDT:USDT", quote_volume=50_000_000),
            MarketTicker(symbol="TICKER_LOW/USDT:USDT", quote_volume=4_999_999),
        ]

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        *,
        since: int | None = None,
        end_ts: int | None = None,
    ) -> pd.DataFrame:
        quote_volume = _quote_volume_for(symbol, timeframe)
        return _quote_volume_frame(
            bars=limit,
            quote_volume_per_bar=quote_volume,
        )


async def _no_sleep(_seconds: float) -> None:
    return None


@pytest.mark.asyncio
async def test_volume_filter_flow_reduces_candidates_at_each_liquidity_stage():
    """Ticker, daily, intraday, and mega-cap filters each remove known symbols."""
    universe_cfg = _test_universe_config()

    pre_backfill = await select_symbols_for_backfill(
        market_data=ControlledVolumeMarketData(),
        universe_cfg=universe_cfg,
        pre_download_end_ts_by_timeframe={
            "1d": 1_800_000_000_000,
            "1m": 1_800_000_000_000,
        },
        prefilter_pause_seconds=0,
        sleep=_no_sleep,
    )

    assert pre_backfill.ticker_count == 5
    assert pre_backfill.after_ticker_liquidity_count == 4
    assert pre_backfill.after_daily_liquidity_count == 3
    assert pre_backfill.after_intraday_liquidity_count == 2
    assert pre_backfill.after_mega_caps_count == 1
    assert pre_backfill.symbols == ["FINAL/USDT:USDT"]


def _quote_volume_for(symbol: str, timeframe: str) -> float:
    if timeframe == "1d":
        return {
            "FINAL/USDT:USDT": 10_000_000,
            "MEGA/USDT:USDT": 10_000_000,
            "INTRADAY_LOW/USDT:USDT": 10_000_000,
            "DAILY_LOW/USDT:USDT": 1_000_000,
        }[symbol]
    return {
        "FINAL/USDT:USDT": 10_000,
        "MEGA/USDT:USDT": 50_000,
        "INTRADAY_LOW/USDT:USDT": 1_000,
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


def _quote_volume_frame(*, bars: int, quote_volume_per_bar: float) -> pd.DataFrame:
    close = 10.0
    volume = quote_volume_per_bar / close
    return pd.DataFrame(
        {
            "timestamp": range(bars),
            "open": [close] * bars,
            "high": [close] * bars,
            "low": [close] * bars,
            "close": [close] * bars,
            "volume": [volume] * bars,
        }
    )
