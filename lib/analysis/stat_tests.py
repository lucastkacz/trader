import numpy as np
import pandas as pd
import statsmodels.api as sm
from lib.utils.logger import setup_logger

logger = setup_logger(__name__)

def calculate_half_life(spread: pd.Series) -> float:
    """
    Calculates the half-life of mean reversion using the Ornstein-Uhlenbeck process.
    
    Formula: dx(t) = -lambda * (x(t) - mean) * dt + sigma * dW(t)
    Discretized: x(t) - x(t-1) = alpha + beta * x(t-1) + epsilon
    Half-life = -ln(2) / beta
    
    Args:
        spread: The spread series (Asset A - hedge_ratio * Asset B).
        
    Returns:
        float: The half-life in periods (e.g., if timeframe is 1h, result is in hours).
    """
    spread_lag = spread.shift(1)
    spread_ret = spread - spread_lag
    
    # Drop NaNs created by shifting
    spread_ret = spread_ret.dropna()
    spread_lag = spread_lag.dropna()
    
    # Align indices just in case
    common_index = spread_lag.index.intersection(spread_ret.index)
    spread_lag = spread_lag.loc[common_index]
    spread_ret = spread_ret.loc[common_index]
    
    # Run OLS regression
    spread_lag_const = sm.add_constant(spread_lag)
    model = sm.OLS(spread_ret, spread_lag_const)
    res = model.fit()
    
    beta = res.params.iloc[1]
    
    # If beta >= 0, the process is not mean-reverting (it's trending or random walk)
    if beta >= 0:
        return np.inf
        
    half_life = -np.log(2) / beta
    return half_life

def calculate_hurst_exponent(time_series: pd.Series, max_lags: int = 100) -> float:
    """
    Calculates the Hurst Exponent to determine the time series memory.
    
    H < 0.5: Mean Reverting
    H = 0.5: Random Walk (Brownian Motion)
    H > 0.5: Trending
    
    Args:
        time_series: The spread series.
        max_lags: Maximum lags to calculate (default 100).
        
    Returns:
        float: The Hurst Exponent.
    """
    lags = range(2, min(max_lags, len(time_series) // 2))
    
    # Calculate variance of differences for each lag
    # tau = sqrt(std(series[lag:] - series[:-lag]))
    tau = []
    
    for lag in lags:
        # Difference between price at t and t+lag
        diff = np.subtract(time_series[lag:].values, time_series[:-lag].values)
        tau.append(np.sqrt(np.std(diff)))
    
    # Perform linear regression on log-log scale
    # log(tau) = H * log(lag) + C
    
    try:
        m = np.polyfit(np.log(lags), np.log(tau), 1)
        hurst = m[0] * 2.0  # Adjusting for the specific variance calculation method
        return hurst
    except Exception as e:
        logger.error(f"Error calculating Hurst Exponent: {e}")
        return 0.5

def calculate_zscore(series: pd.Series, window: int = 20) -> pd.Series:
    """
    Calculates the rolling Z-Score of the series.
    
    Z = (Value - Mean) / StdDev
    
    Args:
        series: The spread series.
        window: Rolling window size (e.g., matching half-life).
        
    Returns:
        pd.Series: Z-Score series.
    """
    r = series.rolling(window=window)
    m = r.mean()
    s = r.std()
    z_score = (series - m) / s
    return z_score

def filter_tradable_pairs(
    pairs: list[dict], 
    max_half_life: float = 24.0, 
    max_hurst: float = 0.5
) -> list[dict]:
    """
    Step 3 of the Funnel: Statistical Filtering.
    Filters cointegrated pairs to ensure they are actually tradable (mean-reverting).
    
    Args:
        pairs: List of pair dictionaries (output from cointegration step).
        max_half_life: Maximum acceptable half-life (e.g., 24 hours).
        max_hurst: Maximum Hurst Exponent (0.5 implies random walk, <0.5 implies mean reversion).
        
    Returns:
        List[Dict]: Filtered list of pairs.
    """
    tradable = []
    
    for pair in pairs:
        hl = pair.get('half_life', float('inf'))
        hurst = pair.get('hurst_exponent', 1.0)
        
        # Check Half-Life (must be positive and effectively short enough)
        # Note: infinite half-life means non-mean-reverting
        if 0 < hl <= max_half_life:
            # Check Hurst Exponent (strict mean reversion is < 0.5)
            # We allow slightly higher (e.g. 0.6) sometimes, but strictly it should be < 0.5
            if hurst <= max_hurst:
                tradable.append(pair)
            else:
                logger.debug(f"Dropped {pair['symbol_a']}-{pair['symbol_b']}: Hurst {hurst:.2f} > {max_hurst}")
        else:
            logger.debug(f"Dropped {pair['symbol_a']}-{pair['symbol_b']}: Half-Life {hl:.1f} > {max_half_life}")
            
    logger.info(f"Statistical Filter: {len(tradable)} pairs remaining out of {len(pairs)}.")
    return tradable
