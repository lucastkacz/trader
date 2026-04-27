"""
Tests for the Signal Engine.
Injects synthetic DataFrames to verify Z-score signals match expected behavior.
"""

import numpy as np
import pandas as pd

from src.engine.trader.signal_engine import evaluate_signal


def _make_df(prices, symbol="TEST/USDT"):
    """Helper to build a minimal OHLCV DataFrame from a price array."""
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=len(prices), freq="4h"),
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
        "volume": np.ones(len(prices)) * 1000,
    })
    df.attrs["symbol"] = symbol
    return df


def test_flat_signal_when_zscore_inside_threshold():
    """When spread is within entry bounds, signal should be FLAT."""
    np.random.seed(42)
    n = 200
    # Two assets with nearly identical random walks → Z-score stays near 0
    base = np.cumsum(np.random.randn(n) * 0.01) + 5.0
    noise = np.random.randn(n) * 0.001

    df_a = _make_df(np.exp(base), "A/USDT")
    df_b = _make_df(np.exp(base + noise), "B/USDT")

    result = evaluate_signal(
        df_a, df_b, entry_z=2.0, exit_z=0.0, lookback_bars=14*6,
        vol_lookback_bars=14*6, hedge_ratio=1.0, current_side=None
    )

    assert result.signal == "FLAT"
    assert abs(result.z_score) < 2.0  # Should be near zero


def test_long_spread_when_spread_is_deeply_negative():
    """When spread is far below mean, should trigger LONG_SPREAD."""
    n = 200
    base = np.ones(n) * 5.0

    # A drops sharply relative to B on the last few bars
    prices_a = np.exp(base.copy())
    prices_b = np.exp(base.copy())

    # Crush A's price at the end to push Z-score deeply negative
    prices_a[-10:] = prices_a[-10:] * 0.70

    df_a = _make_df(prices_a, "A/USDT")
    df_b = _make_df(prices_b, "B/USDT")

    result = evaluate_signal(
        df_a, df_b, entry_z=2.0, exit_z=0.0, lookback_bars=14*6,
        vol_lookback_bars=14*6, hedge_ratio=1.0, current_side=None
    )

    assert result.signal == "LONG_SPREAD"
    assert result.z_score < -2.0


def test_short_spread_when_spread_is_deeply_positive():
    """When spread is far above mean, should trigger SHORT_SPREAD."""
    n = 200
    base = np.ones(n) * 5.0

    prices_a = np.exp(base.copy())
    prices_b = np.exp(base.copy())

    # Pump A's price at the end to push Z-score deeply positive
    prices_a[-10:] = prices_a[-10:] * 1.50

    df_a = _make_df(prices_a, "A/USDT")
    df_b = _make_df(prices_b, "B/USDT")

    result = evaluate_signal(
        df_a, df_b, entry_z=2.0, exit_z=0.0, lookback_bars=14*6,
        vol_lookback_bars=14*6, hedge_ratio=1.0, current_side=None
    )

    assert result.signal == "SHORT_SPREAD"
    assert result.z_score > 2.0


def test_hold_when_already_in_position():
    """When already in a position and Z-score hasn't reverted, should HOLD."""
    n = 200
    base = np.ones(n) * 5.0
    prices_a = np.exp(base.copy())
    prices_b = np.exp(base.copy())
    prices_a[-10:] = prices_a[-10:] * 0.70

    df_a = _make_df(prices_a, "A/USDT")
    df_b = _make_df(prices_b, "B/USDT")

    result = evaluate_signal(
        df_a, df_b, entry_z=2.0, exit_z=0.0,
        lookback_bars=14 * 6, vol_lookback_bars=14 * 6,
        hedge_ratio=1.0, current_side="LONG_SPREAD"
    )

    # Should hold the existing position (z_score still deeply negative)
    assert result.signal == "LONG_SPREAD"


def test_exit_when_zscore_reverts_to_zero():
    """When in a position and Z-score reverts near zero, should exit to FLAT."""
    np.random.seed(99)
    n = 200
    # Two assets that track each other closely → Z-score stays near 0
    base = np.cumsum(np.random.randn(n) * 0.001) + 5.0
    tiny_noise = np.random.randn(n) * 0.0001

    df_a = _make_df(np.exp(base), "A/USDT")
    df_b = _make_df(np.exp(base + tiny_noise), "B/USDT")

    result = evaluate_signal(
        df_a, df_b, entry_z=2.0, exit_z=0.5,
        lookback_bars=14 * 6, vol_lookback_bars=14 * 6,
        hedge_ratio=1.0, current_side="LONG_SPREAD"
    )

    # Z-score should be near zero with tightly coupled assets → triggers exit
    assert result.signal == "FLAT"


def test_volatility_parity_weights_sum_to_one():
    """Weights should always sum to 1.0."""
    np.random.seed(123)
    n = 200
    prices_a = np.exp(np.cumsum(np.random.randn(n) * 0.05) + 5.0)
    prices_b = np.exp(np.cumsum(np.random.randn(n) * 0.01) + 3.0)

    df_a = _make_df(prices_a, "A/USDT")
    df_b = _make_df(prices_b, "B/USDT")

    result = evaluate_signal(
        df_a, df_b, entry_z=2.0, exit_z=0.0, lookback_bars=14*6,
        vol_lookback_bars=14*6, hedge_ratio=1.0
    )

    assert abs(result.weight_a + result.weight_b - 1.0) < 1e-10

    # A is more volatile, so it should get LESS weight
    assert result.weight_a < result.weight_b


def test_insufficient_data_returns_flat():
    """When data is too short for lookback, should return FLAT safely."""
    prices = np.ones(10) * 100.0
    df_a = _make_df(prices, "A/USDT")
    df_b = _make_df(prices, "B/USDT")

    result = evaluate_signal(
        df_a, df_b, entry_z=2.0, exit_z=0.0, lookback_bars=14*6,
        vol_lookback_bars=14*6, hedge_ratio=1.0
    )

    assert result.signal == "FLAT"
