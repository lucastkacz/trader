"""OHLCV-based liquidity filters for universe construction."""

from dataclasses import dataclass
from typing import Literal

import pandas as pd

OHLCVLiquidityMetric = Literal[
    "mean_quote_volume",
    "median_quote_volume",
    "percentile_quote_volume",
]


@dataclass(frozen=True)
class LiquiditySelection:
    """Selected OHLCV frames and their measured dollar-volume evidence."""

    pool: dict[str, pd.DataFrame]
    dollar_volumes: dict[str, float]


def select_by_quote_volume_metric(
    frames: dict[str, pd.DataFrame],
    *,
    lookback_bars: int,
    metric: OHLCVLiquidityMetric,
    min_value: float,
    percentile: float | None = None,
) -> LiquiditySelection:
    """Select symbols whose recent OHLCV quote-volume metric is above the floor."""
    _validate_parameters(
        lookback_bars=lookback_bars,
        min_value=min_value,
        metric=metric,
        percentile=percentile,
    )

    pool = {}
    dollar_volumes = {}
    for symbol, frame in frames.items():
        value = quote_volume_metric(
            frame,
            lookback_bars=lookback_bars,
            metric=metric,
            percentile=percentile,
        )
        if value is None:
            continue
        if value >= min_value:
            pool[symbol] = frame
            dollar_volumes[symbol] = value
    return LiquiditySelection(pool=pool, dollar_volumes=dollar_volumes)


def quote_volume_metric(
    frame: pd.DataFrame,
    *,
    lookback_bars: int,
    metric: OHLCVLiquidityMetric,
    percentile: float | None = None,
) -> float | None:
    """Calculate a quote-volume metric from recent OHLCV candles."""
    if "close" not in frame.columns or "volume" not in frame.columns:
        return None
    recent = frame.iloc[-lookback_bars:]
    quote_volume = (recent["volume"] * recent["close"]).dropna()
    if quote_volume.empty:
        return None
    if metric == "mean_quote_volume":
        return float(quote_volume.mean())
    if metric == "median_quote_volume":
        return float(quote_volume.median())
    if metric == "percentile_quote_volume":
        if percentile is None:
            raise ValueError("percentile is required for percentile_quote_volume")
        return float(quote_volume.quantile(percentile / 100.0))
    raise ValueError(f"Unsupported OHLCV liquidity metric: {metric}")


def select_by_average_dollar_volume(
    frames: dict[str, pd.DataFrame],
    *,
    lookback_bars: int,
    min_dollar_volume: float,
) -> LiquiditySelection:
    """Select symbols whose recent average OHLCV dollar volume is above the floor."""
    return select_by_quote_volume_metric(
        frames,
        lookback_bars=lookback_bars,
        metric="mean_quote_volume",
        min_value=min_dollar_volume,
    )


def _validate_parameters(
    *,
    lookback_bars: int,
    min_value: float,
    metric: OHLCVLiquidityMetric,
    percentile: float | None,
) -> None:
    if lookback_bars <= 0:
        raise ValueError("lookback_bars must be positive")
    if min_value < 0:
        raise ValueError("min_value must be non-negative")
    if metric == "percentile_quote_volume":
        if percentile is None:
            raise ValueError("percentile is required for percentile_quote_volume")
        if not 0 <= percentile <= 100:
            raise ValueError("percentile must be between 0 and 100")
    elif percentile is not None:
        raise ValueError("percentile is only valid for percentile_quote_volume")
