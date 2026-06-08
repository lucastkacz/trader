"""Mega-cap exclusion filters for universe construction."""

import pandas as pd


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
