"""Research baseline fields for eligible-pair artifacts."""

from typing import Any

import numpy as np
import pandas as pd

from src.engine.analysis.spread_math import (
    build_hedged_log_spread,
    build_log_price_series,
    build_rolling_zscore,
)


def build_research_baseline_fields(
    prices: pd.DataFrame,
    *,
    hedge_ratio: float,
    lookback_bars: int | None,
) -> dict[str, Any]:
    """Build JSON-safe baseline fields from an aligned research price window."""
    aligned = _aligned_prices(prices)
    log_x = build_log_price_series(aligned["asset_x_close"], "asset_x")
    log_y = build_log_price_series(aligned["asset_y_close"], "asset_y")
    spread = build_hedged_log_spread(
        aligned["asset_x_close"],
        aligned["asset_y_close"],
        hedge_ratio,
    )

    fields: dict[str, Any] = {
        "Research_Window": {
            "start": _json_timestamp(aligned.index.min()) if len(aligned) else None,
            "end": _json_timestamp(aligned.index.max()) if len(aligned) else None,
            "bars": int(len(aligned)),
        },
        "Correlation": _finite_or_none(log_x.corr(log_y)),
        "Spread_Mean": _finite_or_none(spread.mean()),
        "Spread_Std": _finite_or_none(spread.std()),
    }
    z_distribution = _z_score_distribution(spread, lookback_bars)
    if z_distribution is not None:
        fields["Z_Score_Distribution"] = z_distribution
    return fields


def apply_research_baseline_fields(
    pair: dict[str, Any],
    prices: pd.DataFrame,
    *,
    lookback_bars: int | None = None,
) -> dict[str, Any]:
    """Return a pair row with baseline fields computed from aligned prices."""
    resolved_lookback = lookback_bars
    if resolved_lookback is None:
        best_params = pair.get("Best_Params")
        if isinstance(best_params, dict):
            resolved_lookback = _positive_int_or_none(best_params.get("lookback_bars"))

    return {
        **pair,
        **build_research_baseline_fields(
            prices,
            hedge_ratio=float(pair["Hedge_Ratio"]),
            lookback_bars=resolved_lookback,
        ),
    }


def prices_from_unified_ohlcv(unified: pd.DataFrame) -> pd.DataFrame:
    """Extract the canonical baseline price columns from stress-filter OHLCV."""
    return pd.DataFrame(
        {
            "asset_x_close": unified["A_close"],
            "asset_y_close": unified["B_close"],
        },
        index=unified.index,
    )


def _aligned_prices(prices: pd.DataFrame) -> pd.DataFrame:
    required = ["asset_x_close", "asset_y_close"]
    missing = [column for column in required if column not in prices.columns]
    if missing:
        raise KeyError(f"Missing baseline price columns: {', '.join(missing)}")
    aligned = prices[required].copy()
    aligned["asset_x_close"] = pd.to_numeric(aligned["asset_x_close"], errors="coerce")
    aligned["asset_y_close"] = pd.to_numeric(aligned["asset_y_close"], errors="coerce")
    return aligned.dropna().sort_index()


def _z_score_distribution(
    spread: pd.Series,
    lookback_bars: int | None,
) -> dict[str, Any] | None:
    if lookback_bars is None or lookback_bars <= 0:
        return None
    z_scores = build_rolling_zscore(
        spread,
        lookback_bars=lookback_bars,
        min_periods=lookback_bars,
    ).dropna()
    return {
        "lookback_bars": int(lookback_bars),
        "observations": int(len(z_scores)),
        "mean": _finite_or_none(z_scores.mean()),
        "std": _finite_or_none(z_scores.std()),
        "min": _finite_or_none(z_scores.min()),
        "max": _finite_or_none(z_scores.max()),
        "p05": _finite_or_none(z_scores.quantile(0.05)) if len(z_scores) else None,
        "p95": _finite_or_none(z_scores.quantile(0.95)) if len(z_scores) else None,
    }


def _positive_int_or_none(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _finite_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(parsed):
        return None
    return parsed


def _json_timestamp(value: Any) -> str | None:
    if pd.isna(value):
        return None
    if isinstance(value, (int, float, np.integer, np.floating)):
        unit = "ms" if abs(float(value)) > 10_000_000_000 else "s"
        return pd.to_datetime(value, unit=unit, utc=True).isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
