import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from src.dashboard.styles import COLORS

def render_zscore_spread(df: pd.DataFrame, asset_a: str, asset_b: str, hedge_ratio: float, rolling_window: int = 30):
    """
    Renders the rolling Z-Score of the spread to visualize mean-reversion 
    entry and exit thresholds for the Classic Cointegration strategy.
    """
    st.write(f"### 📊 Z-Score Spread Dynamics: {asset_a} vs {asset_b}")
    
    # Extract date range from the dataframe assuming index is datetime
    try:
        start_date = df.index.min().strftime('%Y-%m-%d %H:%M')
        end_date = df.index.max().strftime('%Y-%m-%d %H:%M')
        date_str = f"**Period:** `{start_date}` to `{end_date}`"
    except Exception:
        date_str = ""
        
    st.markdown(date_str)
    
    if len(df) < rolling_window:
        st.warning(f"Not enough data points ({len(df)}) to calculate a rolling window of {rolling_window} for the Z-Score.")
        return

    # 1. Calculate the Spread
    # Spread = Price_A - (Hedge_Ratio * Price_B)
    spread = df[asset_a] - (hedge_ratio * df[asset_b])
    
    # 2. Calculate Rolling Mean and Std
    rolling_mean = spread.rolling(window=rolling_window).mean()
    rolling_std = spread.rolling(window=rolling_window).std()
    
    # 3. Calculate Z-Score
    zscore = (spread - rolling_mean) / rolling_std
    
    # Drop NaNs from the warmup period to make the chart clean
    zscore = zscore.dropna()
    
    # Create the Plotly chart
    fig = go.Figure()
    
    # The actual Z-Score line
    fig.add_trace(go.Scatter(
        x=zscore.index,
        y=zscore.values,
        mode='lines',
        name='Z-Score',
        line=dict(color=COLORS['primary'], width=2)
    ))
    
    # Add horizontal lines for typical Entry/Exit thresholds (+2, -2, 0)
    fig.add_hline(y=2.0, line_dash="dash", line_color=COLORS['danger'], annotation_text="Overbought (+2)", annotation_position="top left")
    fig.add_hline(y=-2.0, line_dash="dash", line_color=COLORS['success'], annotation_text="Oversold (-2)", annotation_position="bottom left")
    fig.add_hline(y=0.0, line_dash="dot", line_color=COLORS['text'], annotation_text="Mean (0)", annotation_position="top left", opacity=0.5)
    
    fig.update_layout(
        plot_bgcolor=COLORS['background'],
        paper_bgcolor=COLORS['background'],
        font_color=COLORS['text'],
        margin=dict(l=40, r=40, t=40, b=40),
        xaxis_title="Time",
        yaxis_title="Z-Score (Standard Deviations)",
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"*Showing the {rolling_window}-period Z-Score (driven by your Evaluation/Lookback Window). Trades are typically entered when the line crosses the red/green bands, and exited when it returns to 0.*")
