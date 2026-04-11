import pandas as pd

def calculate_zscore(series: pd.Series, window: int) -> pd.Series:
    """
    Calculates the detailed Z-Score.
    This logic will eventually move to src/strategies.
    """
    epsilon = 1e-8
    mean = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    return (series - mean) / (std + epsilon)
