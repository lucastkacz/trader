"""
Signal Engine
==============
Pure math module for live signal generation.
Structurally identical to the vectorized backtest logic, but operates
on the latest bar rather than a historical array.

ARCHITECTURAL RULE: No CCXT imports allowed in this module.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional

from src.core.logger import logger, LogContext
from src.engine.analysis.spread_math import build_hedged_log_spread, build_rolling_zscore


@dataclass
class SignalResult:
    """Immutable output of a single signal evaluation."""
    signal: str          # LONG_SPREAD | SHORT_SPREAD | FLAT
    z_score: float       # Current Z-Score value
    weight_a: float      # Volatility parity weight for Asset A
    weight_b: float      # Volatility parity weight for Asset B
    spread: float        # Current raw spread value
    price_a: float       # Latest close of Asset A
    price_b: float       # Latest close of Asset B


def evaluate_signal(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    entry_z: float,
    exit_z: float,
    lookback_bars: int,
    vol_lookback_bars: int,
    hedge_ratio: float,
    current_side: Optional[str] = None,
) -> SignalResult:
    """
    Evaluates the current signal state for a pair.

    Parameters
    ----------
    df_a : Recent OHLCV DataFrame for Asset A (must have 'close' column)
    df_b : Recent OHLCV DataFrame for Asset B (must have 'close' column)
    entry_z : Z-score threshold to trigger entry
    exit_z : Z-score threshold to trigger exit (typically 0.0)
    lookback_bars : Rolling window for spread mean/std
    vol_lookback_bars : Rolling window for volatility parity
    hedge_ratio : Canonical hedge ratio for log(A) - hedge_ratio * log(B)
    current_side : Current position state ('LONG_SPREAD', 'SHORT_SPREAD', or None)

    Returns
    -------
    SignalResult with the computed signal, Z-score, and weights.
    """
    # Align on timestamps via inner join
    merged = pd.merge(
        df_a[["timestamp", "close"]].rename(columns={"close": "A_close"}),
        df_b[["timestamp", "close"]].rename(columns={"close": "B_close"}),
        on="timestamp",
        how="inner",
    ).sort_values("timestamp").reset_index(drop=True)

    if len(merged) < lookback_bars + 1:
        return SignalResult(
            signal="FLAT", z_score=0.0,
            weight_a=0.5, weight_b=0.5,
            spread=0.0,
            price_a=float(merged["A_close"].iloc[-1]) if len(merged) > 0 else 0.0,
            price_b=float(merged["B_close"].iloc[-1]) if len(merged) > 0 else 0.0,
        )

    # 1. Canonical hedge-adjusted log spread and rolling z-score
    spread = build_hedged_log_spread(merged["A_close"], merged["B_close"], hedge_ratio)
    z_scores = build_rolling_zscore(spread, lookback_bars)
    z_score = float(z_scores.iloc[-1])

    # 3. Volatility Parity Weights
    ret_a = np.log(merged["A_close"] / merged["A_close"].shift(1))
    ret_b = np.log(merged["B_close"] / merged["B_close"].shift(1))

    vol_a = ret_a.rolling(window=vol_lookback_bars).std().iloc[-1]
    vol_b = ret_b.rolling(window=vol_lookback_bars).std().iloc[-1]

    if vol_a > 0 and vol_b > 0:
        inv_a = 1.0 / vol_a
        inv_b = 1.0 / vol_b
        sum_inv = inv_a + inv_b
        weight_a = float(inv_a / sum_inv)
        weight_b = float(inv_b / sum_inv)
    else:
        weight_a, weight_b = 0.5, 0.5

    # 4. Signal Logic (State Machine)
    #    - If we are FLAT: check entry thresholds
    #    - If we are in a position: check exit threshold
    if current_side is None:
        # No position — evaluate entry
        if z_score <= -entry_z:
            signal = "LONG_SPREAD"     # Spread is undervalued → buy A, sell B
        elif z_score >= entry_z:
            signal = "SHORT_SPREAD"    # Spread is overvalued → sell A, buy B
        else:
            signal = "FLAT"
    else:
        # In a position — evaluate exit (mean reversion)
        if abs(z_score) <= exit_z:
            signal = "FLAT"            # Z-score reverted to mean → close
        else:
            signal = current_side      # Hold current position

    latest_a = float(merged["A_close"].iloc[-1])
    latest_b = float(merged["B_close"].iloc[-1])

    ctx = LogContext(
        pair=f"{df_a.attrs.get('symbol', '?')}/{df_b.attrs.get('symbol', '?')}",
        signal=signal,
    )
    logger.bind(**ctx.model_dump(exclude_none=True)).debug(
        f"Z={z_score:.4f} | wA={weight_a:.4f} wB={weight_b:.4f} | "
        f"A={latest_a:.6f} B={latest_b:.6f}"
    )

    return SignalResult(
        signal=signal,
        z_score=z_score,
        weight_a=weight_a,
        weight_b=weight_b,
        spread=float(spread.iloc[-1]),
        price_a=latest_a,
        price_b=latest_b,
    )
