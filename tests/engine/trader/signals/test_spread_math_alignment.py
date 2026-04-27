import numpy as np
import pandas as pd
import pytest

from src.engine.analysis.spread_math import build_hedged_log_spread
from src.engine.trader.signal_engine import evaluate_signal
from src.simulation.stress_orchestrator import StressTestOrchestrator


def _make_ohlcv(prices: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=len(prices), freq="4h"),
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
        "volume": np.ones(len(prices)),
    })


def test_live_signal_and_stress_test_use_same_hedged_spread_zscore():
    """Live and backtest paths should agree on hedge-adjusted spread math."""
    periods = 160
    lookback_bars = 60
    hedge_ratio = 0.72

    log_b = np.linspace(4.0, 4.2, periods)
    canonical_spread = np.sin(np.linspace(0.0, 5.0, periods)) * 0.01
    canonical_spread[-1] -= 0.04
    log_a = hedge_ratio * log_b + canonical_spread

    prices_a = np.exp(log_a)
    prices_b = np.exp(log_b)

    df_a = _make_ohlcv(prices_a)
    df_b = _make_ohlcv(prices_b)

    live_result = evaluate_signal(
        df_a=df_a,
        df_b=df_b,
        entry_z=2.0,
        exit_z=0.0,
        lookback_bars=lookback_bars,
        vol_lookback_bars=lookback_bars,
        hedge_ratio=hedge_ratio,
        current_side=None,
    )

    stress_df = pd.DataFrame({
        "A_close": prices_a,
        "B_close": prices_b,
    })
    stress_result = StressTestOrchestrator(storage=None).build_zscore(
        stress_df,
        lookback_bars=lookback_bars,
        hedge_ratio=hedge_ratio,
    )
    stress_spread = build_hedged_log_spread(
        stress_df["A_close"],
        stress_df["B_close"],
        hedge_ratio,
    )

    assert live_result.spread == pytest.approx(stress_spread.iloc[-1])
    assert live_result.z_score == pytest.approx(stress_result["z_score"].iloc[-1])
    assert live_result.z_score < -2.0
    assert live_result.signal == "LONG_SPREAD"
