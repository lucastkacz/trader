"""OHLCV-based liquidity filters for universe construction."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class LiquiditySelection:
    """Selected OHLCV frames and their measured dollar-volume evidence."""

    pool: dict[str, pd.DataFrame]
    dollar_volumes: dict[str, float]


def select_by_average_dollar_volume(
    frames: dict[str, pd.DataFrame],
    *,
    lookback_bars: int,
    min_dollar_volume: float,
    max_dollar_volume: float,
) -> LiquiditySelection:
    """Select symbols whose recent average OHLCV dollar volume is in range."""
    if lookback_bars <= 0:
        raise ValueError("lookback_bars must be positive")
    if min_dollar_volume < 0:
        raise ValueError("min_dollar_volume must be non-negative")
    if max_dollar_volume < min_dollar_volume:
        raise ValueError("max_dollar_volume must be greater than or equal to min_dollar_volume")

    pool = {}
    dollar_volumes = {}
    for symbol, frame in frames.items():
        if "close" not in frame.columns or "volume" not in frame.columns:
            continue
        recent = frame.iloc[-lookback_bars:]
        dollar_volume = float((recent["volume"] * recent["close"]).mean())
        if min_dollar_volume <= dollar_volume <= max_dollar_volume:
            pool[symbol] = frame
            dollar_volumes[symbol] = dollar_volume
    return LiquiditySelection(pool=pool, dollar_volumes=dollar_volumes)
