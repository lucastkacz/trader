import numpy as np
import pandas as pd

try:
    from src.engine.analysis.cointegration import CointegrationEngine
except ImportError:
    pass

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
    
    engine = CointegrationEngine()
    
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
