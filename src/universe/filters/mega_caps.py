"""Mega-cap exclusion filters for universe construction."""

from typing import Literal

import pandas as pd

from src.universe.filters.ohlcv_liquidity import quote_volume_metric

MegaCapQuoteVolumeMetric = Literal[
    "mean_quote_volume",
    "median_quote_volume",
]


def exclude_top_by_dollar_volume(
    pool: dict[str, pd.DataFrame],
    dollar_volumes: dict[str, float],
    *,
    exclude_top_n: int,
) -> dict[str, pd.DataFrame]:
    """Remove the top-N symbols by measured dollar volume."""
    if exclude_top_n < 0:
        raise ValueError("exclude_top_n must be non-negative")
    if exclude_top_n == 0:
        return dict(pool)

    sorted_symbols = sorted(
        dollar_volumes,
        key=lambda symbol: dollar_volumes[symbol],
        reverse=True,
    )
    excluded = set(sorted_symbols[:exclude_top_n])
    return {
        symbol: frame
        for symbol, frame in pool.items()
        if symbol not in excluded
    }


def exclude_top_by_quote_volume_metric(
    pool: dict[str, pd.DataFrame],
    *,
    lookback_bars: int,
    metric: MegaCapQuoteVolumeMetric,
    exclude_top_n: int,
) -> dict[str, pd.DataFrame]:
    """Remove the top-N symbols by an explicitly configured quote-volume metric."""
    dollar_volumes = {}
    for symbol, frame in pool.items():
        value = quote_volume_metric(
            frame,
            lookback_bars=lookback_bars,
            metric=metric,
        )
        if value is not None:
            dollar_volumes[symbol] = value
    return exclude_top_by_dollar_volume(
        pool,
        dollar_volumes,
        exclude_top_n=exclude_top_n,
    )
