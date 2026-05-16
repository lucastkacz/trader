import numpy as np
import pandas as pd
import pytest

from src.engine.trader.config import load_backtest_config

try:
    from src.simulation.vectorized_engine import Simulator
    from src.simulation.friction_model import FrictionEngine
except ImportError:
    pass

def test_friction_engine_requires_explicit_backtest_assumptions():
    with pytest.raises(TypeError):
        FrictionEngine()

def test_pessimism_and_funding_drag():
    """
    Synthesize an artificial Z-Score curve and exact High/Low bars.
    Proves that the simulator forces entries strictly at the Highs/Lows
    (slippage pessimism) and that Friction Engine bleeds the Gross PnL.
    """
    np.random.seed(42)
    # Simulate 5 days of hourly bars
    periods = 120
    dates = pd.date_range("2023-01-01", periods=periods, freq="h")
    
    # 1. Base Prices
    # Let's assume Asset crosses Z-score threshold at bar 10, exits bar 50.
    close_a = np.ones(periods) * 100
    high_a = close_a + 2  # Pessimistic Long cost is 102
    low_a = close_a - 2   # Pessimistic Short cost is 98
    
    close_b = np.ones(periods) * 50
    high_b = close_b + 1
    low_b = close_b - 1
    
    # Synthetic target z-score (Long A, Short B)
    z_scores = np.zeros(periods)
    z_scores[10:50] = -2.5 # Triggers LONG Asset A, SHORT Asset B
    z_scores[50:] = 0.0    # Triggers EXIT
    
    df = pd.DataFrame({
        "timestamp": dates,
        "A_close": close_a, "A_high": high_a, "A_low": low_a,
        "B_close": close_b, "B_high": high_b, "B_low": low_b,
        "z_score": z_scores
    })
    
    # 2. Run simulation
    sim = Simulator()
    gross_df = sim.run(df, entry_z=2.0, exit_z=0.0)
    
    # Assert positions exist
    # Position should be 1.0 (Long) starting at index 11 (T+1 execution)
    assert gross_df["position"].iloc[11] == 1.0
    assert gross_df["position"].iloc[9] == 0.0
    assert gross_df["signal"].iloc[50] == 0.0
    assert gross_df["position"].iloc[50] == 1.0
    assert gross_df["position"].iloc[51] == 0.0
    
    # Assert the entry friction was calculated against the High/Low, not Close!
    # Because we long A at T+1, we pay the High (102 instead of 100).
    # Because we short B at T+1, we get the Low (49 instead of 50).
    # So our gross return from Entry is instantly negative compared to Mid price.
    assert gross_df["gross_returns"].iloc[11] < 0.0 
    
    # 3. Apply Friction (Funding Rate bleed & Fees)
    friction_cfg = load_backtest_config("configs/backtest/stress_test.yml").friction
    friction = FrictionEngine(
        maker_fee=friction_cfg.maker_fee,
        taker_fee=friction_cfg.taker_fee,
        annual_fund_rate=friction_cfg.annual_fund_rate,
    )
    net_df = friction.apply(gross_df)
    
    raw_pnl = gross_df["gross_returns"].sum()
    net_pnl = net_df["net_returns"].sum()
    
    # Absolute Truth: Net PnL must be strictly worse than Theoretical Gross PnL
    assert net_pnl < raw_pnl


def test_simulator_long_spread_exits_when_z_crosses_mean_with_zero_exit_band():
    periods = 20
    df = _flat_ohlcv_frame(periods)
    df["z_score"] = [0.0] * 5 + [-2.5] * 5 + [-0.5, -0.1, 0.1, 0.3] + [0.0] * 6

    gross_df = Simulator().run(df, entry_z=2.0, exit_z=0.0)

    assert gross_df["signal"].iloc[5] == 1.0
    assert gross_df["position"].iloc[6] == 1.0
    assert gross_df["signal"].iloc[12] == 0.0
    assert gross_df["position"].iloc[12] == 1.0
    assert gross_df["position"].iloc[13] == 0.0


def test_simulator_short_spread_exits_when_z_crosses_mean_with_zero_exit_band():
    periods = 20
    df = _flat_ohlcv_frame(periods)
    df["z_score"] = [0.0] * 5 + [2.5] * 5 + [0.5, 0.1, -0.1, -0.3] + [0.0] * 6

    gross_df = Simulator().run(df, entry_z=2.0, exit_z=0.0)

    assert gross_df["signal"].iloc[5] == -1.0
    assert gross_df["position"].iloc[6] == -1.0
    assert gross_df["signal"].iloc[12] == 0.0
    assert gross_df["position"].iloc[12] == -1.0
    assert gross_df["position"].iloc[13] == 0.0


def test_simulator_uses_exit_band_side_aware():
    periods = 20
    long_df = _flat_ohlcv_frame(periods)
    long_df["z_score"] = [0.0] * 5 + [-2.5] * 5 + [-0.4, -0.2, 0.0] + [0.0] * 7
    short_df = _flat_ohlcv_frame(periods)
    short_df["z_score"] = [0.0] * 5 + [2.5] * 5 + [0.4, 0.2, 0.0] + [0.0] * 7

    long_result = Simulator().run(long_df, entry_z=2.0, exit_z=0.25)
    short_result = Simulator().run(short_df, entry_z=2.0, exit_z=0.25)

    assert long_result["signal"].iloc[10] == 1.0
    assert long_result["signal"].iloc[11] == 0.0
    assert short_result["signal"].iloc[10] == -1.0
    assert short_result["signal"].iloc[11] == 0.0


def _flat_ohlcv_frame(periods):
    dates = pd.date_range("2023-01-01", periods=periods, freq="h")
    close_a = np.ones(periods) * 100
    close_b = np.ones(periods) * 50
    return pd.DataFrame({
        "timestamp": dates,
        "A_close": close_a,
        "A_high": close_a + 2,
        "A_low": close_a - 2,
        "B_close": close_b,
        "B_high": close_b + 1,
        "B_low": close_b - 1,
    })
