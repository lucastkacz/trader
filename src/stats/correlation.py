import pandas as pd
import numpy as np
from typing import Tuple

def calculate_correlation_matrix(prices: pd.DataFrame, method: str = 'pearson', min_periods: int = 30) -> pd.DataFrame:
    """
    Calculates the correlation matrix of asset returns.
    
    Args:
        prices (pd.DataFrame): DataFrame of asset prices (DatetimeIndex, Symbols as columns).
        method (str): Correlation method ('pearson', 'kendall', 'spearman').
        min_periods (int): Minimum number of observations required per pair.
        
    Returns:
        pd.DataFrame: Correlation matrix.
    """
    # Use logarithmic returns, not absolute prices for correlation to avoid spurious correlation
    # and to ensure returns are symmetric and additive
    returns = np.log(prices / prices.shift(1)).dropna(how='all')
    return returns.corr(method=method, min_periods=min_periods)

def get_top_correlated_pairs(corr_matrix: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """
    Extracts the top N highly correlated pairs from a correlation matrix.
    
    Returns:
        pd.DataFrame with columns ['Asset_1', 'Asset_2', 'Correlation']
    """
    # Get upper triangle of the correlation matrix (without diagonal)
    upper_tri = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
    
    # Unstack to a series: (Asset_1, Asset_2) -> Correlation
    pairs = upper_tri.unstack().dropna()
    
    # Sort by absolute correlation (handling strong negative correlations as well if desired)
    # For pairs trading, strong positive correlation is standard.
    pairs_sorted = pairs.sort_values(ascending=False)
    
    df_pairs = pairs_sorted.reset_index()
    df_pairs.columns = ['Asset_2', 'Asset_1', 'Correlation'] # Unstack puts row index as level 1, col as level 0
    
    # Reorder for readability
    df_pairs = df_pairs[['Asset_1', 'Asset_2', 'Correlation']]
    
    return df_pairs.head(top_n)
