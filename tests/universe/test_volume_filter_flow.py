import pandas as pd
import pytest

from src.engine.trader.config import load_universe_config
from src.exchange.data.market_data import MarketTicker
from src.universe.filters.ohlcv_liquidity import select_by_quote_volume_metric
from src.universe.selection import select_symbols_for_backfill


class ControlledVolumeMarketData:
    """Fake exchange data where each symbol is designed to fail at one stage."""

    async def fetch_market_tickers(self) -> list[MarketTicker]:
        return [
            MarketTicker(symbol="FINAL/USDT:USDT", quote_volume=50_000_000),
            MarketTicker(symbol="STORED_LOW/USDT:USDT", quote_volume=50_000_000),
            MarketTicker(symbol="PREFILTER_LOW/USDT:USDT", quote_volume=50_000_000),
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
        assert timeframe == "1d"
        daily_quote_volume = {
            "FINAL/USDT:USDT": 10_000_000,
            "STORED_LOW/USDT:USDT": 10_000_000,
            "PREFILTER_LOW/USDT:USDT": 1_000_000,
        }[symbol]
        return _quote_volume_frame(
            bars=limit,
            quote_volume_per_bar=daily_quote_volume,
        )


async def _no_sleep(_seconds: float) -> None:
    return None


@pytest.mark.asyncio
async def test_volume_filter_flow_reduces_candidates_at_each_liquidity_stage():
    """Ticker, prefilter, and stored-data liquidity each remove known symbols."""
    universe_cfg = load_universe_config("configs/universe/dev.yml")

    pre_backfill = await select_symbols_for_backfill(
        market_data=ControlledVolumeMarketData(),
        universe_cfg=universe_cfg,
        prefilter_end_ts=1_800_000_000_000,
        prefilter_pause_seconds=0,
        sleep=_no_sleep,
    )

    assert pre_backfill.ticker_count == 4
    assert pre_backfill.after_ticker_liquidity_count == 3
    assert pre_backfill.after_prefilter_liquidity_count == 2
    assert pre_backfill.symbols == ["FINAL/USDT:USDT", "STORED_LOW/USDT:USDT"]

    stored_cfg = universe_cfg.filters.stored_data_liquidity
    stored_frames = {
        "FINAL/USDT:USDT": _quote_volume_frame(
            bars=stored_cfg.lookback_bars,
            quote_volume_per_bar=10_000,
        ),
        "STORED_LOW/USDT:USDT": _quote_volume_frame(
            bars=stored_cfg.lookback_bars,
            quote_volume_per_bar=1_000,
        ),
    }

    stored_selection = select_by_quote_volume_metric(
        stored_frames,
        lookback_bars=stored_cfg.lookback_bars,
        metric=stored_cfg.metric,
        min_value=stored_cfg.min_value,
        percentile=stored_cfg.percentile,
    )

    assert list(stored_selection.pool) == ["FINAL/USDT:USDT"]
    assert stored_selection.dollar_volumes == {"FINAL/USDT:USDT": 10_000.0}


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
