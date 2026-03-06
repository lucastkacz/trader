import pandas as pd
import numpy as np
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller
from typing import Tuple, List

def calculate_hedge_ratio(price_a: pd.Series, price_b: pd.Series, use_log: bool = True) -> float:
    """
    Calculates the Hedge Ratio (beta) using Ordinary Least Squares (OLS) regression.
    Equation: Price_A = alpha + beta * Price_B
    If use_log is True, runs OLS on log(prices) to handle massive scale disparities (e.g., BTC vs XRP).
    
    Args:
        price_a (pd.Series): Dependent variable (Asset A)
        price_b (pd.Series): Independent variable (Asset B)
        use_log (bool): Use logarithmic prices for calculation
        
    Returns:
        float: The hedge ratio (beta)
    """
    if use_log:
        price_a = np.log(price_a)
        price_b = np.log(price_b)
        
    X = sm.add_constant(price_b)
    model = sm.OLS(price_a, X).fit()
    return model.params.iloc[1] # beta

def test_cointegration(price_a: pd.Series, price_b: pd.Series, use_log: bool = True) -> Tuple[float, float, float]:
    """
    Runs the Engle-Granger two-step cointegration test with optional log scaling.
    
    Returns:
        Tuple: (Hedge Ratio, ADF Statistic, p-value)
    """
    # 1. Hedge Ratio
    beta = calculate_hedge_ratio(price_a, price_b, use_log)
    
    # 2. Spread (Residuals)
    if use_log:
        spread = np.log(price_a) - (beta * np.log(price_b))
    else:
        spread = price_a - (beta * price_b)
    
    # 3. ADF Test on Spread
    adf_result = adfuller(spread.dropna())
    adf_stat = adf_result[0]
    p_value = adf_result[1]
    
    return beta, adf_stat, p_value

def calculate_spread(price_a: pd.Series, price_b: pd.Series, hedge_ratio: float, use_log: bool = True) -> pd.Series:
    """
    Calculates the continuous spread between two assets given a constant hedge ratio.
    """
    if use_log:
        return np.log(price_a) - (hedge_ratio * np.log(price_b))
    return price_a - (hedge_ratio * price_b)

def calculate_rolling_hedge_ratio(price_a: pd.Series, price_b: pd.Series, window: int, use_log: bool = True) -> pd.Series:
    """
    Calculates the rolling Hedge Ratio (beta) using the covariance/variance identity.
    beta = Cov(A, B) / Var(B)
    """
    if use_log:
        price_a = np.log(price_a)
        price_b = np.log(price_b)
        
    cov = price_a.rolling(window=window).cov(price_b)
    var = price_b.rolling(window=window).var()
    # Avoid div by zero
    beta = cov / var.replace(0, pd.NA)
    return beta.fillna(0.0)

def calculate_rolling_spread(price_a: pd.Series, price_b: pd.Series, window: int, use_log: bool = True) -> Tuple[pd.Series, pd.Series]:
    """
    Calculates the dynamic rolling spread based on dynamic rolling beta.
    Spread_t = log(A_t) - (beta_t * log(B_t))
    
    Returns:
        Tuple: (Rolling Spread Series, Rolling Beta Series)
    """
    rolling_beta = calculate_rolling_hedge_ratio(price_a, price_b, window, use_log)
    
    if use_log:
        rolling_spread = np.log(price_a) - (rolling_beta * np.log(price_b))
    else:
        rolling_spread = price_a - (rolling_beta * price_b)
        
    return rolling_spread, rolling_beta

def test_rolling_cointegration(price_a: pd.Series, price_b: pd.Series, window: int, use_log: bool = True) -> Tuple[pd.Series, pd.Series]:
    """
    Runs the Engle-Granger cointegration test over a rolling window.
    WARNING: Iterative ADF tests are computationally heavy.
    """
    rolling_spread, _ = calculate_rolling_spread(price_a, price_b, window, use_log)
    
    adf_stats = []
    p_values = []
    
    # Loop over windows (starting when we have enough data)
    for i in range(len(rolling_spread)):
        if i < window:
            adf_stats.append(pd.NA)
            p_values.append(pd.NA)
            continue
            
        window_spread = rolling_spread.iloc[i-window+1 : i+1]
        
        # Drop NAs
        clean_spread = window_spread.dropna()
        if len(clean_spread) < 20: # arbitrary minimum for ADF
            adf_stats.append(pd.NA)
            p_values.append(pd.NA)
            continue
            
        try:
            res = adfuller(clean_spread)
            adf_stats.append(res[0])
            p_values.append(res[1])
        except Exception:
            adf_stats.append(pd.NA)
            p_values.append(pd.NA)
            
    return pd.Series(adf_stats, index=price_a.index), pd.Series(p_values, index=price_a.index)

