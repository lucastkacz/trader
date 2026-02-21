import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from src.data.loader import load_data

class DataLoader:
    """
    Responsible for loading and aligning data for the Vectorized Engine.
    Ensures:
    1. All symbols are aligned to the same index.
    2. Forward filling of prices (max gap tolerance).
    3. Forward filling of funding rates (critical for perps).
    4. Splitting into Open, High, Low, Close, Volume, Funding matrices.
    """
    
    def __init__(self, symbols: List[str], timeframe: str = '1h'):
        self.symbols = symbols
        self.timeframe = timeframe
        self.data_dict = {}
        
    def load(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Loads data and returns the primary matrices needed for backtesting.
        
        Returns:
            Tuple: (prices, funding_rates, returns)
            - prices: DataFrame of CLOSE prices (aligned)
            - funding_rates: DataFrame of FUNDING rates (aligned & filled)
            - returns: DataFrame of % returns (Close_t / Close_{t-1} - 1)
        """
        # 1. Load raw data from parquet
        self.data_dict = load_data(self.symbols, self.timeframe)
        
        if not self.data_dict:
            raise ValueError("No data loaded. Check symbol names and data availability.")

        # 2. Align timestamps (Outer Join)
        # We use the union of all indices to ensure we don't drop data if one symbol is new.
        all_timestamps =  pd.Index([])
        for df in self.data_dict.values():
            all_timestamps = all_timestamps.union(df.index)
            
        all_timestamps = all_timestamps.sort_values().unique()
        
        # Filter by date range if provided
        if start_date:
            all_timestamps = all_timestamps[all_timestamps >= pd.to_datetime(start_date)]
        if end_date:
            all_timestamps = all_timestamps[all_timestamps <= pd.to_datetime(end_date)]
            
        # Reindex checks
        # Create empty DataFrames for each feature
        close_df = pd.DataFrame(index=all_timestamps)
        open_df = pd.DataFrame(index=all_timestamps) # Needed for execution?
        funding_df = pd.DataFrame(index=all_timestamps)
        
        for symbol, df in self.data_dict.items():
            # Reindex to master timeline
            # ffill limit? Crypto trades 24/7, so gaps are usually real outages.
            # let's ffill a bit (e.g. 1-2 hours) but not too much to avoid fake data.
            # actually, for vector backtest, NaNs are poison. We might need to ffill reasonably or drop rows.
            # For now: ffill 1 step.
            
            aligned = df.reindex(all_timestamps)
            
            # Fill Price Gaps (small ones)
            # aligned['close'] = aligned['close'].ffill(limit=3) 
            # aligned['open'] = aligned['open'].ffill(limit=3)
            
            # Close prices
            close_df[symbol] = aligned['close']
            
            # Open prices (if we want to trade at Open)
            open_df[symbol] = aligned['open']

            # Funding Rates
            # Funding usually comes every 8h. We MUST ffill it until the next change.
            # If the CSV has NaNs for funding except at 00:00, 08:00, 16:00,
            # then ffill is exactly what we want.
            if 'fundingRate' in aligned.columns:
                funding_df[symbol] = aligned['fundingRate'].ffill()
            else:
                funding_df[symbol] = 0.0 # Spot? Or missing data. Assume 0 cost.

        # 3. Final Cleanup
        # If a symbol didn't exist at the start of the timeframe, it will be NaN.
        # We should NOT fill those NaNs with 0, keep them NaN so the strategy knows it's not tradable.
        
        # Funding rate NaNs -> 0 or keep NaN? 
        # If price exists but funding is NaN -> Assume 0 (Spot or nice exchange).
        # If price is NaN -> Funding should be NaN.
        funding_df = funding_df.fillna(0.0) 
        
        # Mask funding where price is NaN (symbol not listing yet)
        funding_df = funding_df.where(close_df.notna(), np.nan)
        
        # Calculate Returns (Close-to-Close? Or Open-to-Open?)
        # For signal generation chains: usually Close-to-Close.
        # For PnL: depends on execution.
        
        return close_df, open_df, funding_df

    def get_opens(self) -> pd.DataFrame:
        """Helper to get Open prices aligned."""
        # TODO: clean this up to be more efficient, maybe return a huge Panel/Dict of DFs
        pass
