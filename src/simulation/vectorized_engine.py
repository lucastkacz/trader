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
        out["signal"] = _build_side_aware_signals(z, entry_z=entry_z, exit_z=exit_z)
        
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


def _build_side_aware_signals(
    z_scores: pd.Series,
    entry_z: float,
    exit_z: float,
) -> pd.Series:
    """Build target spread state using the same side-aware exit policy as live execution."""
    exit_band = abs(exit_z)
    current = 0.0
    signals = []

    for z_score in z_scores:
        if not np.isfinite(z_score):
            signals.append(current)
            continue

        if current == 0.0:
            if z_score <= -entry_z:
                current = 1.0
            elif z_score >= entry_z:
                current = -1.0
        elif current == 1.0:
            if z_score >= -exit_band:
                current = 0.0
        elif current == -1.0:
            if z_score <= exit_band:
                current = 0.0

        signals.append(current)

    return pd.Series(signals, index=z_scores.index)
