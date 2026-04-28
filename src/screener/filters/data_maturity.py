import pandas as pd
from typing import Dict, List
from src.core.logger import logger, LogContext

class DataMaturityFilter:
    """
    Enforces the strict configured data maturity mandate.
    Removes assets that lack sufficient historical depth to
    prove cointegration immunity against macro events.
    """
    
    def __init__(self, min_bars: int):
        self.min_bars = min_bars
        
    def filter(self, pool: Dict[str, pd.DataFrame]) -> List[str]:
        survivors = []
        rejected_count = 0
        
        ctx = LogContext(trade_id="SCREENER_MATURITY")
        
        for symbol, df in pool.items():
            if "close" not in df.columns:
                continue
                
            # We explicitly dropna() to prevent coins with massive 
            # exchange-outage gaps from passing the filter
            valid_rows = len(df["close"].dropna())
            
            if valid_rows >= self.min_bars:
                survivors.append(symbol)
            else:
                rejected_count += 1
                
        logger.bind(**ctx.model_dump(exclude_none=True)).info(
            f"Maturity Sieve Complete. {len(survivors)} passed. {rejected_count} rejected (< {self.min_bars} bars)."
        )
        return survivors
