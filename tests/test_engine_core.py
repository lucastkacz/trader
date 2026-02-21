import pandas as pd
import numpy as np
import pytest
from src.engine.core.engine import VectorizedEngine

def test_engine_identity_buy_hold():
    """
    Test that Buy & Hold 100% matches asset return (minus small fees).
    """
    # 1. Setup Data
    dates = pd.date_range("2023-01-01", periods=10, freq="D")
    prices = pd.DataFrame({"BTC": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]}, index=dates)
    
    # Target: 100% BTC from day 1
    weights = pd.DataFrame({"BTC": [1.0] * 10}, index=dates)
    # Day 0: No position (weights shift 1), Day 1: Enter
    
    engine = VectorizedEngine(initial_capital=100.0, fee_rate=0.0, slippage=0.0, compounding=True)
    results = engine.run(prices, weights)
    
    # Expected:
    # Day 0 (Index 0): Signal 1.0 -> Trade at Index 1 Open (but we use Close-Close here).
    # Engine Logic: shifted_weights[t] = weights[t-1].
    # At t=0: shifted=NaN (0). Return=0.
    # At t=1: shifted=1.0. Return = (101-100)/100 = 1%. 
    # Equity should track price exactly after entry.
    
    # Price 100 -> 109 (+9%)
    # Equity 100 -> should be close to 109.
    
    # Let's check the tail
    final_equity = results['equity'].iloc[-1]
    
    # Note: Logic is:
    # t=0: Alloc=0. Ret=0. Eq=100.
    # t=1: Alloc=1. Ret=(101-100)/100 = 0.01. Eq = 100 * 1.01 = 101.
    # ...
    # t=9: Alloc=1. Ret=(109-108)/108. Eq = ... = 109.
    
    assert np.isclose(final_equity, 109.0, atol=0.01)

def test_funding_costs():
    """
    Test that funding costs reduce equity for Long positions.
    """
    dates = pd.date_range("2023-01-01", periods=5, freq="D")
    prices = pd.DataFrame({"BTC": [100, 100, 100, 100, 100]}, index=dates) # Flat price
    weights = pd.DataFrame({"BTC": [1.0] * 5}, index=dates)
    
    # Funding Rate = 0.01 (1%) per day
    funding = pd.DataFrame({"BTC": [0.01] * 5}, index=dates)
    
    engine = VectorizedEngine(initial_capital=100.0, fee_rate=0.0, slippage=0.0, compounding=False)
    results = engine.run(prices, weights, funding_rates=funding)
    
    # T=0: Flat.
    # T=1: Pos=1. Fund=0.01. Cost = 1.0 * 0.01 = 0.01. Net Ret = -0.01.
    # Equity drops by 0.01 * 100 = 1.
    
    # 4 active days (t=1 to 4). Total drop = 4.
    # Start 100 -> End 96.
    
    final_equity = results['equity'].iloc[-1]
    assert np.isclose(final_equity, 96.0, atol=0.01)

if __name__ == "__main__":
    # fast manual check
    test_engine_identity_buy_hold()
    test_funding_costs()
    print("Tests Passed!")
