import pandas as pd
import numpy as np
from typing import Optional, Dict
from tqdm import tqdm
from lib.analysis.stat_tests import calculate_half_life, calculate_hurst_exponent
from lib.analysis.cointegration import check_cointegration, calculate_hedge_ratio
from lib.utils.logger import setup_logger

logger = setup_logger(__name__)

def calculate_rolling_stats(
    series_a: pd.Series, 
    series_b: pd.Series, 
    window_hours: int = 336, # 14 days * 24h
    step_hours: int = 24     # Step by 1 day
) -> pd.DataFrame:
    """
    Calculates statistical metrics over a rolling window.
    
    Args:
        series_a: Price series of Asset A.
        series_b: Price series of Asset B.
        window_hours: Size of the lookback window in hours (default 14 days).
        step_hours: How much to advance the window each iteration (default 1 day).
        
    Returns:
        pd.DataFrame: DataFrame indexed by window end date, containing rolling stats.
    """
    # Align indices
    common_index = series_a.index.intersection(series_b.index)
    series_a = series_a.loc[common_index]
    series_b = series_b.loc[common_index]
    
    if len(series_a) < window_hours:
        logger.error("Not enough data for rolling analysis.")
        return pd.DataFrame()
        
    results = []
    
    # Iterate using integer indexing for speed
    # We start at 'window_hours' and move by 'step_hours'
    total_len = len(series_a)
    
    logger.info(f"Running rolling analysis (Window={window_hours}h, Step={step_hours}h)...")
    
    for end_idx in tqdm(range(window_hours, total_len, step_hours), desc="Rolling Analysis"):
        start_idx = end_idx - window_hours
        
        # Slice Window
        # Note: iloc is exclusive on the upper bound, so [start:end] gets 'window_size' elements
        win_a = series_a.iloc[start_idx:end_idx]
        win_b = series_b.iloc[start_idx:end_idx]
        
        # Skip if gaps/NaNs (strict check)
        if win_a.isna().any() or win_b.isna().any():
            continue
            
        current_date = win_a.index[-1]
        
        # 1. Correlation (Log Returns)
        # We calculate log returns just for this window
        ret_a = np.log(win_a / win_a.shift(1)).dropna()
        ret_b = np.log(win_b / win_b.shift(1)).dropna()
        
        if len(ret_a) < 2: continue
        
        corr = ret_a.corr(ret_b)
        
        # 2. Cointegration
        try:
            # check_cointegration returns (score, pvalue, critical_val)
            t_stat, p_val, _ = check_cointegration(win_a, win_b)
            beta = calculate_hedge_ratio(win_a, win_b)
            
            # 3. Spread Stats
            spread = win_a - (beta * win_b)
            half_life = calculate_half_life(spread)
            hurst = calculate_hurst_exponent(spread)
            
            results.append({
                'timestamp': current_date,
                'correlation': corr,
                'p_value': p_val,
                'hedge_ratio': beta,
                'half_life': half_life,
                'hurst': hurst
            })
            
        except Exception:
            continue
            
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.set_index('timestamp')
        
    return df
