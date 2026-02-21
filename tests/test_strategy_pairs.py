import pandas as pd
import numpy as np
from src.strategies.pairs import PairsTradingStrategy
from src.engine.core.engine import VectorizedEngine

def generate_mock_cointegrated_data(periods: int = 500) -> pd.DataFrame:
    """
    Generates two artificial price series that are heavily cointegrated.
    Asset_A is a random walk.
    Asset_B = 0.5 * Asset_A + Mean Reverting Noise
    """
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=periods, freq="D")
    
    # Random walk for A
    returns_a = np.random.normal(0, 0.01, periods)
    price_a = 100 * np.exp(np.cumsum(returns_a))
    
    # Cointegrated B
    # Mean reverting noise (Ornstein-Uhlenbeck style approximation)
    noise = np.zeros(periods)
    for i in range(1, periods):
        noise[i] = noise[i-1] + 0.1 * (0 - noise[i-1]) + np.random.normal(0, 0.5)
        
    price_b = 50 + 0.5 * price_a + noise
    
    return pd.DataFrame({"Asset_A": price_a, "Asset_B": price_b}, index=dates)

def test_pairs_strategy_e2e():
    """
    Tests the full pipeline:
    1. Generate mock data
    2. Pairs Strategy 'trains' and finds the pair
    3. Pairs Strategy generates valid target weights
    4. VectorizedEngine runs the backtest
    """
    # 1. Data
    prices = generate_mock_cointegrated_data(500)
    
    # 2. Strategy Init & Train
    strategy = PairsTradingStrategy(
        timeframe='1D',
        zscore_window=20,
        entry_threshold=1.5,
        exit_threshold=0.0,
        capital_per_pair=0.1 # 10% allocation
    )
    
    strategy.train(prices)
    
    # Verify it found our artificially cointegrated pair
    assert ("Asset_A", "Asset_B") in strategy.active_pairs or ("Asset_B", "Asset_A") in strategy.active_pairs, "Failed to find cointegrated pair"
    
    # 3. Generate Weights
    weights = strategy.generate_target_weights(prices)
    
    # Verify dimensions and completeness
    assert weights.shape == prices.shape
    assert not weights.isna().any().any()
    
    # Verify we actually take positions (weights shouldn't be all zero)
    assert np.abs(weights.values).sum() > 0
    
    # 4. Engine Run
    engine = VectorizedEngine(initial_capital=10000, fee_rate=0.0005, slippage=0.0001)
    results = engine.run(prices, weights)
    
    # Verify Engine Output
    assert len(results) == len(prices)
    assert 'equity' in results.columns
    assert 'calc_returns' not in results.columns # Internal sanity check on output columns
    
    final_equity = results['equity'].iloc[-1]
    print(f"\nE2E Test Passed. Final Mock Equity: ${final_equity:.2f}")

if __name__ == "__main__":
    test_pairs_strategy_e2e()
