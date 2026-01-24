import pandas as pd
from typing import Tuple, List

def get_trade_signals(
    z_score_series: pd.Series, 
    entry_threshold: float = 2.0, 
    exit_threshold: float = 0.0, 
    stop_loss: float = 4.0
) -> Tuple[List, List, List]:
    """
    Identifies entry and exit points based on Z-Score.
    
    Args:
        z_score_series: The Z-Score time series.
        entry_threshold: Z-Score to enter a trade (default 2.0).
        exit_threshold: Z-Score to take profit (default 0.0).
        stop_loss: Z-Score to stop loss (default 4.0).
        
    Returns:
        Tuple: (long_entries, short_entries, exits)
        Each is a list of tuples (timestamp, z_value).
    """
    long_entries = []
    short_entries = []
    exits = []
    
    in_position = 0 # 0: None, 1: Long, -1: Short
    
    for i in range(1, len(z_score_series)):
        current_z = z_score_series.iloc[i]
        prev_z = z_score_series.iloc[i-1]
        idx = z_score_series.index[i]
        
        # ENTRY LOGIC
        if in_position == 0:
            # Long Spread (Z < -Entry)
            if current_z < -entry_threshold and prev_z >= -entry_threshold:
                long_entries.append((idx, current_z))
                in_position = 1
            # Short Spread (Z > Entry)
            elif current_z > entry_threshold and prev_z <= entry_threshold:
                short_entries.append((idx, current_z))
                in_position = -1
                
        # EXIT LOGIC
        elif in_position == 1: # Currently Long
            # Crosses 0 (TP) OR Drops below StopLoss (SL)
            if current_z >= exit_threshold or current_z <= -stop_loss:
                exits.append((idx, current_z))
                in_position = 0
                
        elif in_position == -1: # Currently Short
            # Crosses 0 (TP) OR Goes above StopLoss (SL)
            if current_z <= exit_threshold or current_z >= stop_loss:
                exits.append((idx, current_z))
                in_position = 0
                
    return long_entries, short_entries, exits
