from enum import Enum

class MeanReversionMethod(str, Enum):
    """
    Standardized categorization of Statistical Arbitrage / Mean Reversion methods.
    Allows for structured filtering and UI display across the platform.
    """
    CLASSIC_COINTEGRATION = "Classic Cointegration (OLS)"
    OSCILLATOR_DIVERGENCE = "Oscillator Divergence (RSI/MACD)"
    KALMAN_FILTER = "Dynamic Kalman Filter"
    DYNAMIC_TIME_WARPING = "Dynamic Time Warping"
    COPULA_TAIL_DEPENDENCE = "Copula Tail Dependence"
    MACHINE_LEARNING = "Machine Learning Clustering"
    UNKNOWN = "Unknown Method"
