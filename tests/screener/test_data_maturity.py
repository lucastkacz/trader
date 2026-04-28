import pandas as pd
import numpy as np
import pytest

try:
    from src.screener.filters.data_maturity import DataMaturityFilter
except ImportError:
    pass

def test_data_maturity_filter_requires_explicit_min_bars():
    with pytest.raises(TypeError):
        DataMaturityFilter()

def test_data_maturity_rejection():
    """
    Simulates a 179-bar active pandas timeframe to verify the 180-bar
    minimum rule is strictly enforced by the filter.
    """
    # 1. Synthesize 179 bars of data
    dates = pd.date_range(start="2023-01-01", periods=179, freq='D')
    df_young = pd.DataFrame({
        "timestamp": dates,
        "close": np.random.rand(179) * 100
    })
    
    # 2. Synthesize 180 bars of data + outage NaNs
    dates_mature = pd.date_range(start="2023-01-01", periods=185, freq='D')
    closes = np.random.rand(185) * 100
    # Simulate a crash where the exchange disconnected for 10 days
    closes[100:110] = np.nan
    
    df_corrupted = pd.DataFrame({
        "timestamp": dates_mature,
        "close": closes
    })
    
    # 3. Simulate perfect 200 days
    dates_perfect = pd.date_range(start="2023-01-01", periods=200, freq='D')
    df_perfect = pd.DataFrame({
        "timestamp": dates_perfect,
        "close": np.random.rand(200) * 100
    })
    
    # Injected raw payloads dictionary simulating Parquet outputs
    pool = {
        "YOUNG_COIN": df_young,
        "CORRUPT_COIN": df_corrupted,
        "PERFECT_COIN": df_perfect
    }
    
    sieve = DataMaturityFilter(min_bars=180)
    survivors = sieve.filter(pool)
    
    assert len(survivors) == 1
    assert "PERFECT_COIN" in survivors
    assert "YOUNG_COIN" not in survivors
    assert "CORRUPT_COIN" not in survivors
