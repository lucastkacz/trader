import pandas as pd
import numpy as np
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint
from typing import List, Tuple, Dict
from lib.utils.logger import setup_logger
from .stat_tests import calculate_half_life, calculate_hurst_exponent

logger = setup_logger(__name__)

def calculate_hedge_ratio(series_y: pd.Series, series_x: pd.Series) -> float:
    """
    Calculates the hedge ratio (beta) using OLS linear regression.
    Equation: Y = beta * X + alpha
    
    Args:
        series_y: The dependent variable (Target Asset).
        series_x: The independent variable (Hedge Asset).
        
    Returns:
        float: The hedge ratio (beta).
    """
    # Add constant for intercept (alpha)
    x = sm.add_constant(series_x)
    
    model = sm.OLS(series_y, x).fit()
    
    # Return the coefficient of X (beta)
    return model.params.iloc[1]

def calculate_rolling_hedge_ratio(series_y: pd.Series, series_x: pd.Series, window: int) -> pd.Series:
    """
    Calculates the rolling hedge ratio (beta) using rolling Covariance and Variance.
    Beta = Cov(Y, X) / Var(X)
    
    Args:
        series_y: Target Asset (Y)
        series_x: Hedge Asset (X)
        window: Rolling window size.
        
    Returns:
        pd.Series: Rolling Beta.
    """
    cov = series_y.rolling(window=window).cov(series_x)
    var = series_x.rolling(window=window).var()
    
    return cov / var

def check_cointegration(series_y: pd.Series, series_x: pd.Series) -> Tuple[float, float, float]:
    """
    Performs the Engle-Granger cointegration test.
    
    Args:
        series_y: The first asset series.
        series_x: The second asset series.
        
    Returns:
        Tuple: (t-statistic, p-value, critical_value_1%)
    """
    # The 'coint' function returns (t-stat, p-value, critical_values)
    # trend='c' means constant (intercept) is included
    score, pvalue, critical_values = coint(series_y, series_x, trend='c')
    
    # We return the 1% critical value for strict checking
    crit_value_1pct = critical_values[0]
    
    return score, pvalue, crit_value_1pct

def find_cointegrated_pairs(price_matrix: pd.DataFrame, candidates: List[Tuple[str, str, float]], p_value_threshold: float = 0.05) -> List[Dict]:
    """
    Iterates through a list of candidate pairs and checks for cointegration.
    Calculates spread and half-life for valid pairs.
    
    Args:
        price_matrix: DataFrame containing price series for all assets.
        candidates: List of tuples (SymbolA, SymbolB, Correlation).
        p_value_threshold: The threshold for statistical significance (default 0.05).
        
    Returns:
        List[Dict]: A list of cointegrated pairs with stats, hedge ratio, spread, and half-life.
    """
    valid_pairs = []
    
    logger.info(f"Checking cointegration for {len(candidates)} candidate pairs...")
    
    for sym_a, sym_b, corr in candidates:
        try:
            series_a = price_matrix[sym_a]
            series_b = price_matrix[sym_b]
            
            # Run Test
            score, pvalue, crit_val = check_cointegration(series_a, series_b)
            
            if pvalue < p_value_threshold:
                # Calculate Hedge Ratio
                hedge_ratio = calculate_hedge_ratio(series_a, series_b)
                
                # Calculate Spread
                spread = series_a - (hedge_ratio * series_b)
                
                # Calculate Half-Life
                half_life = calculate_half_life(spread)
                
                # Calculate Hurst Exponent
                hurst = calculate_hurst_exponent(spread)
                
                valid_pairs.append({
                    'symbol_a': sym_a,
                    'symbol_b': sym_b,
                    'correlation': corr,
                    'p_value': pvalue,
                    't_stat': score,
                    'hedge_ratio': hedge_ratio,
                    'spread': spread,
                    'half_life': half_life,
                    'hurst_exponent': hurst
                })
        except Exception as e:
            logger.warning(f"Error checking pair {sym_a}-{sym_b}: {e}")
            continue
            
    logger.info(f"Found {len(valid_pairs)} cointegrated pairs out of {len(candidates)}.")
    return valid_pairs
