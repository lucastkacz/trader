import pandas as pd
import numpy as np

class Simulator:
    """
    Vectorized Execution Engine.
    Executes Z-Score thresholds natively across dataframes.
    Enforces extreme slippage pessimism by punishing entries at wick extremes.
    """
    
    def run(self, df: pd.DataFrame, entry_z: float = 2.0, exit_z: float = 0.0) -> pd.DataFrame:
        out = df.copy()
        
        # 1. State Triggers (1 = Long Spread, -1 = Short Spread, 0 = Flat)
        z = out["z_score"]
        signals = np.where(z <= -entry_z, 1.0, np.where(z >= entry_z, -1.0, np.nan))
        signals = np.where((z > -exit_z) & (z < exit_z), 0.0, signals)
        
        out["signal"] = pd.Series(signals).ffill().fillna(0.0)
        
        # We can only enter the market on the NEXT bar after the signal
        out["position"] = out["signal"].shift(1).fillna(0.0)
        
        # 2. Extreme Slippage Simulation (The Pessimistic Mandate)
        # Identify exact entry transition bars
        is_entry_long = (out["position"] == 1.0) & (out["position"].shift(1) == 0.0)
        is_entry_short = (out["position"] == -1.0) & (out["position"].shift(1) == 0.0)
        
        # Standard Close-to-Close returns for carrying a position
        ret_A = np.log(out["A_close"] / out["A_close"].shift(1))
        ret_B = np.log(out["B_close"] / out["B_close"].shift(1))
        
        # Punish the Entry Long: Buy A at the High, Sell B at the Low
        pessimistic_entry_ret_A_long = np.log(out["A_close"] / out["A_high"].shift(1))
        pessimistic_entry_ret_B_short = np.log(out["B_close"] / out["B_low"].shift(1))
        
        # Punish the Entry Short: Sell A at the Low, Buy B at the High
        pessimistic_entry_ret_A_short = np.log(out["A_close"] / out["A_low"].shift(1))
        pessimistic_entry_ret_B_long = np.log(out["B_close"] / out["B_high"].shift(1))
        
        # Apply the logic natively
        out["trade_ret_A"] = np.where(is_entry_long, pessimistic_entry_ret_A_long, 
                             np.where(is_entry_short, pessimistic_entry_ret_A_short, ret_A))
                             
        out["trade_ret_B"] = np.where(is_entry_long, pessimistic_entry_ret_B_short, 
                             np.where(is_entry_short, pessimistic_entry_ret_B_long, ret_B))
                             
        # 3. Spread Gross Returns
        # Long Spread = +A, -B
        # Short Spread = -A, +B
        gross = out["position"] * (out["trade_ret_A"] - out["trade_ret_B"])
        out["gross_returns"] = gross.fillna(0.0)
        
        return out
