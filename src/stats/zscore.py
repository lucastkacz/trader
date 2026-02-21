import pandas as pd

def calculate_z_score(spread: pd.Series, window: int = 30) -> pd.Series:
    """
    Calculates the Rolling Z-Score of a given spread.
    Z = (Spread - Rolling Mean) / Rolling Std
    
    Args:
        spread (pd.Series): The spread to normalize.
        window (int): Lookback window for mean and standard deviation.
        
    Returns:
        pd.Series: The Z-Score series.
    """
    rolling_mean = spread.rolling(window=window).mean()
    rolling_std = spread.rolling(window=window).std()
    
    # Avoid division by zero when std is 0
    z_score = (spread - rolling_mean) / rolling_std.replace(0, pd.NA)
    
    return z_score.fillna(0.0)

def generate_signals(
    z_score: pd.Series, 
    entry_threshold: float = 2.0, 
    exit_threshold: float = 0.0
) -> pd.DataFrame:
    """
    Translates a Z-Score series into generic +/- 1 signals for a single spread.
    
    Logic:
    If Z > entry_threshold => Sell Spread (-1) (Spread too high)
    If Z < -entry_threshold => Buy Spread (+1) (Spread too low)
    If Z crosses exit_threshold => Flat (0) (Mean Reversion complete)
    
    Args:
        z_score (pd.Series): The rolling Z-score.
        entry_threshold (float): Z-score required to enter a trade.
        exit_threshold (float): Z-score required to exit a trade (crosses 0).
        
    Returns:
        pd.DataFrame: A DataFrame with the Z-score and the generated Position.
    """
    # 1. Initialize DataFrame
    df = pd.DataFrame(index=z_score.index)
    df['z_score'] = z_score
    df['position'] = 0.0 # 0 = Flat, 1 = Long Spread, -1 = Short Spread
    
    # We need to maintain state. In pandas vector land, this is tricky.
    # Usually requires a state machine or clever forward filling.
    # Here is a standard vector approach using mask and ffill.
    
    # Entry signals
    long_entry = df['z_score'] < -entry_threshold
    short_entry = df['z_score'] > entry_threshold
    
    # Exit signals (crossing zero)
    # If Long, we exit when Z > exit_threshold
    # If Short, we exit when z < -exit_threshold
    long_exit = df['z_score'] >= exit_threshold
    short_exit = df['z_score'] <= -exit_threshold
    
    # Create target state column
    df.loc[long_entry, 'target_state'] = 1.0
    df.loc[short_entry, 'target_state'] = -1.0
    
    # For exits, we set state back to 0
    # Note: Long exit shouldn't override short entry on same bar (though theoretically shouldn't gap past 2.0).
    df.loc[long_exit & (df['z_score'] > 0), 'target_state'] = df.loc[long_exit & (df['z_score'] > 0), 'target_state'].fillna(0.0)
    df.loc[short_exit & (df['z_score'] < 0), 'target_state'] = df.loc[short_exit & (df['z_score'] < 0), 'target_state'].fillna(0.0)

    # Fill NaN states with 0 initially to catch the very first rows before any signal
    df['target_state'] = df['target_state'].ffill().fillna(0.0)
    
    # The pure 'crosses zero' exit logic is famously hard in pure Pandas without iteration
    # Let's iterate over rows for safety. It's an indicator, speed is less paramount than engine speed here.
    
    positions = []
    current_pos = 0.0
    
    for _, row in df.iterrows():
        z = row['z_score']
        
        # Check Exits
        if current_pos == 1.0 and z >= exit_threshold:
            current_pos = 0.0
        elif current_pos == -1.0 and z <= -exit_threshold:
            current_pos = 0.0
            
        # Check Entries
        if current_pos == 0.0:
            if z < -entry_threshold:
                current_pos = 1.0
            elif z > entry_threshold:
                current_pos = -1.0
                
        positions.append(current_pos)
        
    df['position'] = positions
    return df
