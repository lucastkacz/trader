import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller
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
