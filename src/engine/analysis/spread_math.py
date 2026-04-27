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


def build_hedged_log_spread(
    asset_x_close: pd.Series,
    asset_y_close: pd.Series,
    hedge_ratio: float,
) -> pd.Series:
    """Build the canonical hedge-adjusted log-price spread."""
    return np.log(asset_x_close) - hedge_ratio * np.log(asset_y_close)


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
