"""
Shared spread construction utilities.

The canonical trader spread is:

    log(asset_x) - hedge_ratio * log(asset_y)

Keeping this in one place prevents discovery, backtest, and live signal
paths from silently trading different definitions of the same pair.
"""

import numpy as np
import pandas as pd
from typing import Optional


def require_positive_finite_prices(prices: pd.Series, label: str) -> pd.Series:
    """Return numeric raw prices, rejecting data that cannot be logged safely."""
    numeric = pd.to_numeric(prices, errors="coerce")
    invalid = numeric.isna() | ~np.isfinite(numeric) | (numeric <= 0)
    if len(numeric) == 0 or invalid.any():
        raise ValueError(f"{label} prices must be positive finite raw prices")
    return numeric.astype(float)


def build_log_price_series(prices: pd.Series, label: str) -> pd.Series:
    """Convert positive finite raw prices to log prices exactly once."""
    return np.log(require_positive_finite_prices(prices, label))


def build_hedged_log_spread(
    asset_x_close: pd.Series,
    asset_y_close: pd.Series,
    hedge_ratio: float,
) -> pd.Series:
    """Build the canonical hedge-adjusted spread from raw positive prices."""
    log_x = build_log_price_series(asset_x_close, "asset_x")
    log_y = build_log_price_series(asset_y_close, "asset_y")
    return log_x - hedge_ratio * log_y


def build_rolling_zscore(
    spread: pd.Series,
    lookback_bars: int,
    min_periods: Optional[int] = None,
) -> pd.Series:
    """Compute rolling z-scores for a spread series."""
    periods = lookback_bars if min_periods is None else min_periods
    rolling_mean = spread.rolling(window=lookback_bars, min_periods=periods).mean()
    rolling_std = spread.rolling(window=lookback_bars, min_periods=periods).std()
    rolling_std = rolling_std.replace(0.0, np.nan)
    return (spread - rolling_mean) / rolling_std
