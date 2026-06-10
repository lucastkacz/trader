"""Pre-backfill universe symbol selection."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pandas as pd

from src.core.logger import logger
from src.data.sync.models import MarketDataAdapter, Sleep
from src.engine.trader.config import UniverseConfig
from src.universe.filters.mega_caps import exclude_top_by_quote_volume_metric
from src.universe.filters.market_tickers import select_symbols_by_quote_volume
from src.universe.filters.ohlcv_liquidity import select_by_quote_volume_metric
from src.utils.timeframe_math import get_timeframe_minutes


@dataclass(frozen=True)
class UniverseSelectionResult:
    """Traceable result of the pre-backfill universe selection."""

    symbols: list[str]
    ticker_count: int
    after_ticker_liquidity_count: int
    after_daily_liquidity_count: int
    after_intraday_liquidity_count: int
    after_mega_caps_count: int
    daily_liquidity_failures: dict[str, str]
    intraday_liquidity_failures: dict[str, str]


async def select_symbols_for_backfill(
    *,
    market_data: MarketDataAdapter,
    universe_cfg: UniverseConfig,
    pre_download_end_ts_by_timeframe: dict[str, int],
    prefilter_pause_seconds: float = 0,
    sleep: Sleep | None = None,
) -> UniverseSelectionResult:
    """Select symbols using cheap tickers plus optional temporary OHLCV prefilters."""
    sleep = sleep or asyncio.sleep
    pre_download = universe_cfg.filters.pre_download
    tickers = await market_data.fetch_market_tickers()
    ticker_cfg = pre_download.ticker_liquidity
    if ticker_cfg.enabled:
        symbols = select_symbols_by_quote_volume(
            tickers,
            min_quote_volume=ticker_cfg.min_24h_quote_volume,
        )
    else:
        symbols = [ticker.symbol for ticker in tickers]

    after_ticker_count = len(symbols)

    daily_cfg = pre_download.daily_liquidity
    daily_failures: dict[str, str] = {}
    if daily_cfg.enabled and symbols:
        daily_frames, daily_failures = await _fetch_ohlcv_frames(
            market_data=market_data,
            symbols=symbols,
            timeframe=daily_cfg.timeframe,
            lookback_bars=daily_cfg.lookback_bars,
            end_ts=_end_ts_for(
                daily_cfg.timeframe,
                pre_download_end_ts_by_timeframe,
            ),
            pause_seconds=prefilter_pause_seconds,
            sleep=sleep,
        )
        selection = select_by_quote_volume_metric(
            daily_frames,
            lookback_bars=daily_cfg.lookback_bars,
            metric=daily_cfg.metric,
            min_value=daily_cfg.min_value,
            percentile=daily_cfg.percentile,
        )
        symbols = list(selection.pool)
    after_daily_count = len(symbols)

    intraday_cfg = pre_download.intraday_liquidity
    intraday_failures: dict[str, str] = {}
    intraday_frames = {}
    if intraday_cfg.enabled and symbols:
        intraday_frames, intraday_failures = await _fetch_ohlcv_frames(
            market_data=market_data,
            symbols=symbols,
            timeframe=intraday_cfg.timeframe,
            lookback_bars=intraday_cfg.lookback_bars,
            end_ts=_end_ts_for(
                intraday_cfg.timeframe,
                pre_download_end_ts_by_timeframe,
            ),
            pause_seconds=prefilter_pause_seconds,
            sleep=sleep,
        )
        selection = select_by_quote_volume_metric(
            intraday_frames,
            lookback_bars=intraday_cfg.lookback_bars,
            metric=intraday_cfg.metric,
            min_value=intraday_cfg.min_value,
            percentile=intraday_cfg.percentile,
        )
        symbols = list(selection.pool)
        intraday_frames = selection.pool
    after_intraday_count = len(symbols)

    mega_cfg = pre_download.mega_caps
    if mega_cfg.exclude_top_n > 0 and symbols:
        if (
            not intraday_frames
            or mega_cfg.timeframe != intraday_cfg.timeframe
            or mega_cfg.lookback_bars > intraday_cfg.lookback_bars
        ):
            intraday_frames, intraday_failures = await _fetch_ohlcv_frames(
                market_data=market_data,
                symbols=symbols,
                timeframe=mega_cfg.timeframe,
                lookback_bars=mega_cfg.lookback_bars,
                end_ts=_end_ts_for(
                    mega_cfg.timeframe,
                    pre_download_end_ts_by_timeframe,
                ),
                pause_seconds=prefilter_pause_seconds,
                sleep=sleep,
            )
        ranked_pool = exclude_top_by_quote_volume_metric(
            {
                symbol: intraday_frames[symbol]
                for symbol in symbols
                if symbol in intraday_frames
            },
            lookback_bars=mega_cfg.lookback_bars,
            metric=mega_cfg.metric,
            exclude_top_n=mega_cfg.exclude_top_n,
        )
        symbols = list(ranked_pool)
    after_mega_count = len(symbols)

    logger.info(
        "Universe selection complete: "
        f"tickers={len(tickers)} "
        f"after_ticker_liquidity={after_ticker_count} "
        f"after_daily_liquidity={after_daily_count} "
        f"after_intraday_liquidity={after_intraday_count} "
        f"after_mega_caps={after_mega_count} "
        f"daily_failures={len(daily_failures)} "
        f"intraday_failures={len(intraday_failures)}"
    )
    return UniverseSelectionResult(
        symbols=symbols,
        ticker_count=len(tickers),
        after_ticker_liquidity_count=after_ticker_count,
        after_daily_liquidity_count=after_daily_count,
        after_intraday_liquidity_count=after_intraday_count,
        after_mega_caps_count=after_mega_count,
        daily_liquidity_failures=daily_failures,
        intraday_liquidity_failures=intraday_failures,
    )


def _prefilter_start_ts(*, end_ts: int, timeframe: str, lookback_bars: int) -> int:
    bar_ms = int(get_timeframe_minutes(timeframe) * 60_000)
    return end_ts - lookback_bars * bar_ms


async def _fetch_ohlcv_frames(
    *,
    market_data: MarketDataAdapter,
    symbols: list[str],
    timeframe: str,
    lookback_bars: int,
    end_ts: int,
    pause_seconds: float,
    sleep: Sleep,
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    start_ts = _prefilter_start_ts(
        end_ts=end_ts,
        timeframe=timeframe,
        lookback_bars=lookback_bars,
    )
    frames = {}
    failures = {}
    for symbol in symbols:
        try:
            frame = await market_data.fetch_ohlcv(
                symbol,
                timeframe,
                lookback_bars,
                since=start_ts,
                end_ts=end_ts,
            )
        except Exception as exc:
            failures[symbol] = f"{type(exc).__name__}: {exc}"
            continue
        if not frame.empty:
            frames[symbol] = frame
        else:
            failures[symbol] = "NO_DATA: exchange_returned_no_rows"
        await sleep(pause_seconds)
    return frames, failures


def _end_ts_for(timeframe: str, end_ts_by_timeframe: dict[str, int]) -> int:
    try:
        return end_ts_by_timeframe[timeframe]
    except KeyError as exc:
        raise ValueError(f"missing pre-download end timestamp for {timeframe}") from exc
