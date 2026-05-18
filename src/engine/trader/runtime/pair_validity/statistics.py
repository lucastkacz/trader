"""Statistical drift calculations for pair-validity diagnostics."""

import math
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tools.sm_exceptions import MissingDataError
from statsmodels.tsa.stattools import adfuller

from src.engine.analysis.spread_math import (
    build_hedged_log_spread,
    build_log_price_series,
)


def compute_recent_stats(recent: pd.DataFrame | None) -> dict[str, float]:
    """Compute recent relationship diagnostics from aligned close data."""
    if recent is None or len(recent) < 3:
        return {}
    try:
        log_x = build_log_price_series(recent["asset_x_close"], "asset_x")
        log_y = build_log_price_series(recent["asset_y_close"], "asset_y")
        canonical_reg = sm.OLS(log_x, sm.add_constant(log_y)).fit()
        hedge_ratio = float(canonical_reg.params.iloc[1])
        spread = build_hedged_log_spread(
            recent["asset_x_close"],
            recent["asset_y_close"],
            hedge_ratio,
        )
        return {
            "hedge_ratio": hedge_ratio,
            "correlation": float(log_x.corr(log_y)),
            "p_value": bidirectional_adf_p_value(log_x, log_y),
            "half_life": half_life(spread),
            "spread_mean": float(spread.mean()),
            "spread_std": float(spread.std()),
        }
    except (MissingDataError, ValueError, np.linalg.LinAlgError):
        return {}


def bidirectional_adf_p_value(log_x: pd.Series, log_y: pd.Series) -> float:
    reg_y_on_x = sm.OLS(log_y, sm.add_constant(log_x)).fit()
    reg_x_on_y = sm.OLS(log_x, sm.add_constant(log_y)).fit()
    return float(min(adfuller(reg_y_on_x.resid)[1], adfuller(reg_x_on_y.resid)[1]))


def half_life(spread: pd.Series) -> float:
    values = spread.dropna().to_numpy()
    if len(values) < 3:
        return float("nan")
    z_lag = values[:-1]
    dz = values[1:] - z_lag
    reg = sm.OLS(dz, sm.add_constant(z_lag)).fit()
    lambda_val = float(reg.params[1])
    if lambda_val >= 0:
        return float("inf")
    return float(-np.log(2) / lambda_val)


def finite_optional(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def pct_drift(baseline: float | None, recent: float | None) -> float | None:
    if baseline is None or recent is None or baseline == 0:
        return None
    return ((recent - baseline) / abs(baseline)) * 100.0


def delta(baseline: float | None, recent: float | None) -> float | None:
    if baseline is None or recent is None:
        return None
    return recent - baseline


def safe_ratio(numerator: int | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def spread_mean_shift_sigma(
    baseline_mean: float | None,
    recent_mean: float | None,
    baseline_std: float | None,
) -> float | None:
    if baseline_mean is None or recent_mean is None or baseline_std in (None, 0):
        return None
    return (recent_mean - baseline_mean) / baseline_std

