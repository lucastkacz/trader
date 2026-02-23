import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller
from typing import Tuple, List
from typing import Tuple

def calculate_hedge_ratio(price_a: pd.Series, price_b: pd.Series) -> float:
    """
    Calculates the Hedge Ratio (beta) using Ordinary Least Squares (OLS) regression.
    Equation: Price_A = alpha + beta * Price_B
    
    Args:
        price_a (pd.Series): Dependent variable (Asset A)
        price_b (pd.Series): Independent variable (Asset B)
        
    Returns:
        float: The hedge ratio (beta)
    """
    # We want to find how much of B we need to hedge A.
    X = sm.add_constant(price_b)
    model = sm.OLS(price_a, X).fit()
    return model.params.iloc[1] # beta

def test_cointegration(price_a: pd.Series, price_b: pd.Series) -> Tuple[float, float, float]:
    """
    Runs the Engle-Granger two-step cointegration test.
    1. Find Hedge Ratio via OLS.
    2. Run Augmented Dickey-Fuller (ADF) test on the spread to check for stationarity.
    
    Returns:
        Tuple: (Hedge Ratio, ADF Statistic, p-value)
    """
    # 1. Hedge Ratio
    beta = calculate_hedge_ratio(price_a, price_b)
    
    # 2. Spread (Residuals)
    spread = price_a - (beta * price_b)
    
    # 3. ADF Test on Spread
    # p-value < 0.05 indicates strong evidence of cointegration (stationarity)
    adf_result = adfuller(spread)
    adf_stat = adf_result[0]
    p_value = adf_result[1]
    
    return beta, adf_stat, p_value

def calculate_spread(price_a: pd.Series, price_b: pd.Series, hedge_ratio: float) -> pd.Series:
    """
    Calculates the continuous spread between two assets given a constant hedge ratio.
    """
    return price_a - (hedge_ratio * price_b)

def calculate_rolling_hedge_ratio(price_a: pd.Series, price_b: pd.Series, window: int) -> pd.Series:
    """
    Calculates the rolling Hedge Ratio (beta) using the covariance/variance identity
    for massive speedup over looping OLS computations.
    
    beta = Cov(A, B) / Var(B)
    """
    cov = price_a.rolling(window=window).cov(price_b)
    var = price_b.rolling(window=window).var()
    # Avoid div by zero
    beta = cov / var.replace(0, pd.NA)
    return beta.fillna(0.0)

def calculate_rolling_spread(price_a: pd.Series, price_b: pd.Series, window: int) -> Tuple[pd.Series, pd.Series]:
    """
    Calculates the rolling spread: Spread_t = A_t - (beta_t * B_t)
    Returns:
        Tuple: (Rolling Spread Series, Rolling Beta Series)
    """
    rolling_beta = calculate_rolling_hedge_ratio(price_a, price_b, window)
    rolling_spread = price_a - (rolling_beta * price_b)
    return rolling_spread, rolling_beta

def test_rolling_cointegration(price_a: pd.Series, price_b: pd.Series, window: int) -> Tuple[pd.Series, pd.Series]:
    """
    Runs the Engle-Granger cointegration test over a rolling window.
    WARNING: Iterative ADF tests are computationally heavy.
    
    Returns:
        Tuple: (Rolling ADF Statistics, Rolling P-Values)
    """
    rolling_spread, _ = calculate_rolling_spread(price_a, price_b, window)
    
    adf_stats = []
    p_values = []
    
    # Loop over windows (starting when we have enough data)
    for i in range(len(rolling_spread)):
        if i < window:
            adf_stats.append(pd.NA)
            p_values.append(pd.NA)
            continue
            
        # Get the spread window
        # We need to test the stationarity of the spread formed by the *current* beta
        # across the historically recent window. 
        # Actually, standard rolling Johansen/Engle-Granger tests the residual of the rolling OLS.
        # We will test the last `window` observations of the dynamically created spread.
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
