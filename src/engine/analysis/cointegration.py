import pandas as pd
import numpy as np
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller

class CointegrationEngine:
    """
    Mathematical Core for evaluating pairs.
    It strictly implements:
    1. Bidirectional ADF (Engle-Granger) to prevent asymmetric bias.
    2. EW-OLS (Exponentially Weighted OLS) for drift mitigation.
    3. Ornstein-Uhlenbeck Half-Life for funding decay projection.
    """
    
    def __init__(self, p_value_threshold: float = 0.05, max_half_life: float = 14.0, ewma_span: int = 48):
        self.p_value_threshold = p_value_threshold
        self.max_half_life = max_half_life
        self.ewma_span = ewma_span # Empirically weighting the last ~48 hours
        
    def evaluate(self, series_x: pd.Series, series_y: pd.Series) -> dict:
        """
        Receives purely logarithmic prices (ln(X) and ln(Y)) and returns
        the structural state of the pair.
        """
        # Direction 1: Y = beta * X
        reg_1 = sm.OLS(series_y, sm.add_constant(series_x)).fit()
        adf_1 = adfuller(reg_1.resid)
        pval_1 = adf_1[1]
        
        # Direction 2: X = beta * Y
        reg_2 = sm.OLS(series_x, sm.add_constant(series_y)).fit()
        adf_2 = adfuller(reg_2.resid)
        pval_2 = adf_2[1]
        
        # Select the direction with the tightest co-movement
        if pval_1 <= pval_2:
            p_value = pval_1
            dependent = series_y
            independent = series_x
        else:
            p_value = pval_2
            dependent = series_x
            independent = series_y
            
        # 1. Cointegration Check
        if p_value > self.p_value_threshold:
            return {
                "is_cointegrated": False,
                "p_value": p_value,
                "hedge_ratio": 0.0,
                "half_life": 0.0
            }
            
        # 2. EW-OLS Beta calculation
        # We use a decaying weight matrix to favor the recent drift (last 48 bars).
        alpha = 2.0 / (self.ewma_span + 1)
        weights = np.array([(1 - alpha)**(len(dependent) - i - 1) for i in range(len(dependent))])
        
        ew_ols = sm.WLS(dependent, sm.add_constant(independent), weights=weights).fit()
        hedge_ratio = ew_ols.params.iloc[1]
        
        # 3. Half-Life (Ornstein-Uhlenbeck)
        # We calculate the residual of the standard OLS to model the raw physics of the spread
        residuals = dependent - (ew_ols.params.iloc[0] + hedge_ratio * independent)
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
            
        is_valid = (half_life > 0) and (half_life <= self.max_half_life)
        
        return {
            "is_cointegrated": is_valid,
            "p_value": p_value,
            "hedge_ratio": hedge_ratio,
            "half_life": half_life
        }
