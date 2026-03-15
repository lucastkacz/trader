import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from src.strategies.pairs.weighting import calculate_beta_neutral_weights

def plot_target_weights(weights: pd.DataFrame, rolling_beta: pd.Series, asset_a: str, asset_b: str):
    """
    Renders a Plotly chart showing the continuous theoretical Beta-Neutral weights over time.
    """
    st.markdown("#### ⚖️ Theoretical Beta-Neutral Portfolio Weights")
    st.caption("Visualizing the continuous optimal capital allocation dictated by the dynamic Hedge Ratio. The engine "
               "will \"lock in\" the specific weight from this curve exactly at the moment a trade is triggered.")
    
    # Calculate the continuous theoretical weights (without the position/trade-locking mask)
    # We can reconstruct them quickly here for visualization
    safe_beta = rolling_beta.ffill().fillna(1.0)
    total_exposure = 1.0 + safe_beta.abs()
    
    weight_a_raw = 1.0 / total_exposure
    weight_b_raw = -safe_beta / total_exposure
    
    abs_weight_a = weight_a_raw.abs().clip(lower=0.15, upper=0.85)
    abs_weight_b = weight_b_raw.abs().clip(lower=0.15, upper=0.85)
    
    clipped_sum = abs_weight_a + abs_weight_b
    final_abs_a = abs_weight_a / clipped_sum
    final_abs_b = abs_weight_b / clipped_sum
    
    theoretical_weight_a = final_abs_a * 1.0
    theoretical_weight_b = final_abs_b * 1.0
    
    fig_weights = go.Figure()
    
    fig_weights.add_trace(go.Scatter(
        x=theoretical_weight_a.index, y=theoretical_weight_a, name=f"Theoretical {asset_a}",
        line=dict(color='#00E676', width=2),
    ))
    
    fig_weights.add_trace(go.Scatter(
        x=theoretical_weight_b.index, y=theoretical_weight_b, name=f"Theoretical {asset_b}",
        line=dict(color='#29B6F6', width=2),
    ))
    
    fig_weights.update_layout(
        height=250,
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=60, r=40, t=20, b=40),
        yaxis=dict(title="Absolute Allocation", tickformat=".0%", range=[0, 1.1]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    
    st.plotly_chart(fig_weights, use_container_width=True)
