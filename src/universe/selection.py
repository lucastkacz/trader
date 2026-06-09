"""Pre-backfill universe symbol selection."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from src.core.logger import logger
from src.data.sync.models import MarketDataAdapter, Sleep
from src.engine.trader.config import UniverseConfig
from src.universe.filters.market_tickers import select_symbols_by_quote_volume
from src.universe.filters.ohlcv_liquidity import select_by_quote_volume_metric
from src.utils.timeframe_math import get_timeframe_minutes


@dataclass(frozen=True)
class UniverseSelectionResult:
    """Traceable result of the pre-backfill universe selection."""

    symbols: list[str]
    ticker_count: int
    after_ticker_liquidity_count: int
    after_prefilter_liquidity_count: int
    prefilter_failures: dict[str, str]


async def select_symbols_for_backfill(
    *,
    market_data: MarketDataAdapter,
    universe_cfg: UniverseConfig,
    prefilter_end_ts: int,
    prefilter_pause_seconds: float = 0,
    sleep: Sleep | None = None,
) -> UniverseSelectionResult:
    """Select symbols using cheap tickers plus optional temporary OHLCV prefilters."""
    sleep = sleep or asyncio.sleep
    tickers = await market_data.fetch_market_tickers()
    ticker_cfg = universe_cfg.filters.ticker_liquidity
    if ticker_cfg.enabled:
        symbols = select_symbols_by_quote_volume(
            tickers,
            min_quote_volume=ticker_cfg.min_24h_quote_volume,
        )
    else:
        symbols = [ticker.symbol for ticker in tickers]

    after_ticker_count = len(symbols)

    prefilter_cfg = universe_cfg.filters.prefilter_liquidity
    prefilter_failures: dict[str, str] = {}
    if prefilter_cfg.enabled and symbols:
        frames = {}
        prefilter_start_ts = _prefilter_start_ts(
            end_ts=prefilter_end_ts,
            timeframe=prefilter_cfg.timeframe,
            lookback_bars=prefilter_cfg.lookback_bars,
        )
        for symbol in symbols:
            try:
                frame = await market_data.fetch_ohlcv(
                    symbol,
                    prefilter_cfg.timeframe,
                    prefilter_cfg.lookback_bars,
                    since=prefilter_start_ts,
                    end_ts=prefilter_end_ts,
                )
            except Exception as exc:
                prefilter_failures[symbol] = f"{type(exc).__name__}: {exc}"
                continue
            if not frame.empty:
                frames[symbol] = frame
            await sleep(prefilter_pause_seconds)
        selection = select_by_quote_volume_metric(
            frames,
            lookback_bars=prefilter_cfg.lookback_bars,
            metric=prefilter_cfg.metric,
            min_value=prefilter_cfg.min_value,
            percentile=prefilter_cfg.percentile,
        )
        symbols = list(selection.pool)

    logger.info(
        "Universe selection complete: "
        f"tickers={len(tickers)} "
        f"after_ticker_liquidity={after_ticker_count} "
        f"after_prefilter_liquidity={len(symbols)} "
        f"prefilter_failures={len(prefilter_failures)}"
    )
    return UniverseSelectionResult(
        symbols=symbols,
        ticker_count=len(tickers),
        after_ticker_liquidity_count=after_ticker_count,
        after_prefilter_liquidity_count=len(symbols),
        prefilter_failures=prefilter_failures,
    )


def _prefilter_start_ts(*, end_ts: int, timeframe: str, lookback_bars: int) -> int:
    bar_ms = int(get_timeframe_minutes(timeframe) * 60_000)
    return end_ts - lookback_bars * bar_ms
