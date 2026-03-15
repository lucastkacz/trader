import pandas as pd
import numpy as np

def calculate_beta_neutral_weights(df_pair: pd.DataFrame, signals_df: pd.DataFrame, rolling_beta: pd.Series, asset_a: str, asset_b: str) -> pd.DataFrame:
    """
    Calculates dynamic Beta-Neutral target portfolio weights based on the rolling Hedge Ratio.
    Implements safety guardrails to ensure no single asset exceeds 85% or drops below 15% of capital allocation.
    Locks the weight at the moment of trade entry to prevent continuous rebalancing.
    """
    positions = signals_df['position']
    weights = pd.DataFrame(0.0, index=df_pair.index, columns=df_pair.columns)
    
    # Forward-fill NaNs in beta. If completely missing, default to 1.0 
    # (A beta of 1.0 mathematically results in an exact 0.5 / -0.5 weight split)
    safe_beta = rolling_beta.ffill().fillna(1.0)
    
    # Calculate baseline dynamic weights
    total_exposure = 1.0 + safe_beta.abs()
    weight_a_raw = 1.0 / total_exposure
    weight_b_raw = -safe_beta / total_exposure
    
    # Implement Safety Clipping: constrain absolute weights between 15% and 85%
    abs_weight_a = weight_a_raw.abs().clip(lower=0.15, upper=0.85)
    abs_weight_b = weight_b_raw.abs().clip(lower=0.15, upper=0.85)
    
    # Re-normalize to ensure the absolute sum equals exactly 1.0 (100% capital)
    clipped_sum = abs_weight_a + abs_weight_b
    final_abs_a = abs_weight_a / clipped_sum
    final_abs_b = abs_weight_b / clipped_sum
    
    # Restore directional signs (Asset A is +1.0 base, Asset B takes the inverse sign of beta)
    sign_b = np.where(safe_beta >= 0, -1, 1)
    final_weight_a = final_abs_a * 1.0
    final_weight_b = final_abs_b * sign_b
    
    # --- PREVENT CONTINUOUS REBALANCING ---
    # The rolling beta changes every bar, causing weights to fluctuate. We must "lock in" 
    # the target weight at the moment a trade is entered and hold it constant.
    
    # Identify bars where a new position is taken (changes from 0 to 1/-1, or flips 1 to -1)
    is_entry = (positions != 0) & (positions != positions.shift(1).fillna(0))
    
    # Sample weights only at entries
    entry_weight_a = pd.Series(np.nan, index=df_pair.index)
    entry_weight_b = pd.Series(np.nan, index=df_pair.index)
    
    entry_weight_a.loc[is_entry] = final_weight_a.loc[is_entry]
    entry_weight_b.loc[is_entry] = final_weight_b.loc[is_entry]
    
    # Forward-fill the entry weights so they remain constant for the duration of the trade
    locked_weight_a = entry_weight_a.ffill().fillna(0.0)
    locked_weight_b = entry_weight_b.ffill().fillna(0.0)
    
    # Multiply the locked dynamic weights by the strategy position signal (+1, 0, -1)
    weights[asset_a] = positions * locked_weight_a
    weights[asset_b] = positions * locked_weight_b
    
    return weights.fillna(0.0)
