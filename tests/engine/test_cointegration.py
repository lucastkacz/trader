import numpy as np
import pandas as pd
import pytest

from src.engine.trader.config import load_universe_config

try:
    from src.engine.analysis.cointegration import CointegrationEngine
except ImportError:
    pass

def test_cointegration_engine_requires_explicit_config():
    with pytest.raises(TypeError):
        CointegrationEngine()

def test_bidirectional_adf_and_halflife():
    """
    Synthesize two random walks that are tightly cointegrated
    and prove the engine detects a p-value < 0.05 and a valid Half-Life.
    Also prove it rejects entirely random, divergent walks.
    """
    np.random.seed(42)
    
    # Simulating 500 periods
    n = 500
    
    # 1. Divergent Random Walks (Should FAIL cointegration)
    random_walk_x = np.cumsum(np.random.normal(0, 1, n)) + 100
    random_walk_y = np.cumsum(np.random.normal(0, 1, n)) + 100
    
    df_divergent = pd.DataFrame({"X": random_walk_x, "Y": random_walk_y})
    
    # 2. Cointegrated Random Walks (Should PASS)
    # Y is mathematically tethered to X by a hedge ratio of 0.8
    cointegrated_y = 0.8 * random_walk_x + np.random.normal(0, 0.5, n) + 50
    df_cointegrated = pd.DataFrame({"X": random_walk_x, "Y": cointegrated_y})
    
    universe_cfg = load_universe_config("configs/universe/dev.yml")
    engine = CointegrationEngine(
        p_value_threshold=universe_cfg.cointegration.p_value_threshold,
        max_half_life_bars=30.0,
        ewma_span_bars=universe_cfg.cointegration.ewma_span_bars,
    )
    
    # Test 1: Rejection of divergence
    result_fail = engine.evaluate(df_divergent["X"], df_divergent["Y"])
    assert not result_fail["is_cointegrated"]
    assert result_fail["p_value"] > 0.05
    
    # Test 2: Acceptance of architectural tether
    result_pass = engine.evaluate(df_cointegrated["X"], df_cointegrated["Y"])
    assert result_pass["is_cointegrated"]
    assert result_pass["p_value"] < 0.05
    assert result_pass["hedge_ratio"] > 0.0  # Beta exists
    
    # Test 3: Half-Life should be realistic (not extremely high or 0)
    assert result_pass["half_life"] > 0
    assert result_pass["half_life"] < 30 # Since noise is small, mean reversion is fast


def test_cointegration_returns_canonical_x_on_y_hedge_ratio():
    """Stored hedge ratio should match downstream spread: X - beta * Y."""
    np.random.seed(7)
    n = 500
    log_y = np.cumsum(np.random.normal(0, 0.01, n)) + 4.0
    log_x = 1.7 * log_y + np.random.normal(0, 0.001, n)

    universe_cfg = load_universe_config("configs/universe/dev.yml")
    result = CointegrationEngine(
        p_value_threshold=universe_cfg.cointegration.p_value_threshold,
        max_half_life_bars=1000.0,
        ewma_span_bars=universe_cfg.cointegration.ewma_span_bars,
    ).evaluate(
        pd.Series(np.exp(log_x)),
        pd.Series(np.exp(log_y)),
    )

    assert result["is_cointegrated"]
    assert result["hedge_ratio"] == pytest.approx(1.7, rel=0.02)


def test_cointegration_logs_raw_prices_once():
    np.random.seed(11)
    n = 700
    log_y = np.cumsum(np.random.normal(0, 0.003, n)) + 5.0
    log_x = 0.6 * log_y + np.random.normal(0, 0.0005, n)

    universe_cfg = load_universe_config("configs/universe/dev.yml")
    result = CointegrationEngine(
        p_value_threshold=universe_cfg.cointegration.p_value_threshold,
        max_half_life_bars=1000.0,
        ewma_span_bars=universe_cfg.cointegration.ewma_span_bars,
    ).evaluate(
        pd.Series(np.exp(log_x)),
        pd.Series(np.exp(log_y)),
    )

    assert result["is_cointegrated"]
    assert result["hedge_ratio"] == pytest.approx(0.6, rel=0.02)


def test_cointegration_rejects_non_positive_or_non_finite_raw_prices():
    engine = CointegrationEngine(
        p_value_threshold=0.05,
        max_half_life_bars=100.0,
        ewma_span_bars=20,
    )

    with pytest.raises(ValueError, match="positive finite raw prices"):
        engine.evaluate(
            pd.Series([100.0, 101.0, 0.0, 103.0]),
            pd.Series([50.0, 51.0, 52.0, 53.0]),
        )

    with pytest.raises(ValueError, match="positive finite raw prices"):
        engine.evaluate(
            pd.Series([100.0, 101.0, np.inf, 103.0]),
            pd.Series([50.0, 51.0, 52.0, 53.0]),
        )
