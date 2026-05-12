import pandas as pd
import numpy as np
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller

from src.engine.analysis.spread_math import build_log_price_series

class CointegrationEngine:
    """
    Mathematical Core for evaluating pairs.
    It strictly implements:
    1. Bidirectional ADF (Engle-Granger) to prevent asymmetric bias.
    2. EW-OLS (Exponentially Weighted OLS) for drift mitigation.
    3. Ornstein-Uhlenbeck Half-Life for funding decay projection.
    """
    
    def __init__(
        self,
        p_value_threshold: float,
        max_half_life_bars: float,
        ewma_span_bars: int,
    ):
        self.p_value_threshold = p_value_threshold
        self.max_half_life_bars = max_half_life_bars
        self.ewma_span_bars = ewma_span_bars
        
    def evaluate(self, series_x: pd.Series, series_y: pd.Series) -> dict:
        """
        Receives raw positive prices and returns the structural state of the pair.

        The engine converts to log prices once at this boundary. Downstream
        spread math uses the same raw-price contract.
        """
        log_x = build_log_price_series(series_x, "series_x")
        log_y = build_log_price_series(series_y, "series_y")

        # Direction 1: Y = beta * X
        reg_1 = sm.OLS(log_y, sm.add_constant(log_x)).fit()
        adf_1 = adfuller(reg_1.resid)
        pval_1 = adf_1[1]
        
        # Direction 2: X = beta * Y
        reg_2 = sm.OLS(log_x, sm.add_constant(log_y)).fit()
        adf_2 = adfuller(reg_2.resid)
        pval_2 = adf_2[1]
        
        # Select the direction with the tightest co-movement
        if pval_1 <= pval_2:
            p_value = pval_1
        else:
            p_value = pval_2
            
        # 1. Cointegration Check
        if p_value > self.p_value_threshold:
            return {
                "is_cointegrated": False,
                "p_value": p_value,
                "hedge_ratio": 0.0,
                "half_life": 0.0
            }
            
        # 2. Canonical EW-OLS Beta calculation.
        # Downstream strategy code defines spread as X - beta * Y, so the
        # stored hedge ratio is always the beta from X ~ Y, even though the
        # cointegration pass/fail test above remains bidirectional.
        alpha = 2.0 / (self.ewma_span_bars + 1)
        weights = np.array([(1 - alpha)**(len(log_x) - i - 1) for i in range(len(log_x))])

        ew_ols = sm.WLS(log_x, sm.add_constant(log_y), weights=weights).fit()
        hedge_ratio = ew_ols.params.iloc[1]

        # 3. Half-Life (Ornstein-Uhlenbeck) on the canonical downstream spread.
        residuals = (log_x - hedge_ratio * log_y) - ew_ols.params.iloc[0]
        z = residuals.values
        
        z_lag = z[:-1]
        dz = z[1:] - z_lag
        
        # dz_t = lambda * z_{t-1} + error
        ou_reg = sm.OLS(dz, sm.add_constant(z_lag)).fit()
        lambda_val = ou_reg.params[1]
        
        # If lambda is >= 0, the process is diverging, no mean reversion
        if lambda_val >= 0:
            half_life = float("inf")
        else:
            half_life = -np.log(2) / lambda_val
            
        is_valid = (half_life > 0) and (half_life <= self.max_half_life_bars)
        
        return {
            "is_cointegrated": is_valid,
            "p_value": p_value,
            "hedge_ratio": hedge_ratio,
            "half_life": half_life
        }
