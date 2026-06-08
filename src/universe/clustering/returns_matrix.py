import pandas as pd
import numpy as np
from typing import Dict
from src.core.logger import logger, LogContext

class MatrixBuilder:
    """
    Transforms raw price data into a unified Log-Returns Matrix.
    Applies strict mathematical Winsorization to prevent Pump-and-Dump
    anomalies from permanently destroying correlation topologies.
    """
    def __init__(self, clip_percentile: float):
        self.clip_percentile = clip_percentile
        self.logger_ctx = LogContext(trade_id="SCREENER_MATRIX")
        
    def build(self, pool: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        returns_dict = {}
        
        for symbol, df in pool.items():
            # 1. Natural Logarithm Transformation
            # ln(Pt) - ln(Pt-1) prevents ratio scaling distortions
            log_returns = np.log(df["close"] / df["close"].shift(1))
            
            # 2. Strict NaN Eradication Mandate
            # We forward-fill up to 1 day of missing data, anything else drops.
            log_returns = log_returns.ffill(limit=1).dropna()
            
            if len(log_returns) == 0:
                continue
                
            # 3. Winsorization (The Anti-Scam Shield)
            # Clip the extremes at 1% and 99%
            lower_bound = log_returns.quantile(self.clip_percentile)
            upper_bound = log_returns.quantile(1.0 - self.clip_percentile)
            
            clipped_returns = log_returns.clip(lower=lower_bound, upper=upper_bound)
            returns_dict[symbol] = clipped_returns
            
        # 4. Bind into unified matrix aligned by index (timestamps)
        master_matrix = pd.DataFrame(returns_dict)
        
        # Drop any remaining unaligned NaNs across the common timeline
        master_matrix = master_matrix.dropna()
        
        logger.bind(**self.logger_ctx.model_dump(exclude_none=True)).debug(
            f"Matrix built: {master_matrix.shape[1]} assets over {master_matrix.shape[0]} timestamps."
        )
        
        return master_matrix
