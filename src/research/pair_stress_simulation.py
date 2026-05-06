"""Simulation helpers for pair stress filtering."""

from typing import Any

import numpy as np
import pandas as pd

from src.engine.analysis.spread_math import build_hedged_log_spread, build_rolling_zscore
from src.simulation.friction_model import FrictionEngine
from src.simulation.vectorized_engine import Simulator


def build_pair_zscore(
    df: pd.DataFrame,
    lookback_bars: int,
    hedge_ratio: float,
) -> pd.DataFrame:
    spread = build_hedged_log_spread(df["A_close"], df["B_close"], hedge_ratio)
    df["z_score"] = build_rolling_zscore(
        spread,
        lookback_bars,
        min_periods=lookback_bars,
    )
    return df


def inject_volatility_parity(df: pd.DataFrame, vol_lookback_bars: int) -> pd.DataFrame:
    ret_a = np.log(df["A_close"] / df["A_close"].shift(1))
    ret_b = np.log(df["B_close"] / df["B_close"].shift(1))

    vol_a = ret_a.rolling(window=vol_lookback_bars, min_periods=vol_lookback_bars).std()
    vol_b = ret_b.rolling(window=vol_lookback_bars, min_periods=vol_lookback_bars).std()

    inv_a = 1.0 / vol_a
    inv_b = 1.0 / vol_b
    sum_inv = inv_a + inv_b

    df["weight_A"] = (inv_a / sum_inv).fillna(0.5)
    df["weight_B"] = (inv_b / sum_inv).fillna(0.5)
    return df


def simulate_parameter_set(
    unified: pd.DataFrame,
    hedge_ratio: float,
    lookback_bars: int,
    entry_z: float,
    exit_z: float,
    simulator: Simulator,
    friction: FrictionEngine,
) -> pd.DataFrame | None:
    df = build_pair_zscore(unified.copy(), lookback_bars, hedge_ratio)
    df = df.dropna(subset=["z_score"]).reset_index(drop=True)
    if len(df) < 200:
        return None

    gross_df = simulator.run(df, entry_z=entry_z, exit_z=exit_z)
    gross_df["gross_returns"] = gross_df["position"] * (
        gross_df["weight_A"] * gross_df["trade_ret_A"]
        - gross_df["weight_B"] * gross_df["trade_ret_B"]
    )
    gross_df["gross_returns"] = gross_df["gross_returns"].fillna(0.0)
    return friction.apply(gross_df)


def build_performance_stats(net_df: pd.DataFrame, bars_per_year: int) -> dict[str, Any]:
    equity = net_df["net_returns"].cumsum()
    rolling_max = equity.cummax()
    drawdown = equity - rolling_max
    trades = (net_df["position"].diff().abs() > 0).sum()
    returns_std = net_df["net_returns"].std()
    sharpe = (
        (net_df["net_returns"].mean() / returns_std) * np.sqrt(bars_per_year)
        if returns_std > 0
        else 0.0
    )
    return {
        "final_pnl_pct": round(net_df["net_returns"].sum() * 100, 4),
        "max_drawdown_pct": round(drawdown.min() * 100, 4),
        "sharpe_ratio": round(sharpe, 4),
        "total_trades": int(trades),
        "bars_tested": len(net_df),
    }
