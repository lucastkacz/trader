import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def render_data_alignment(df_pair: pd.DataFrame, asset_a: str, asset_b: str):
    """
    Renders Module 1: Data Alignment.
    Normalizes the prices of Asset A and Asset B to start at 100
    so their relative performance and correlation can be visualized.
    """
    st.write("### 📈 Module 1: Data Alignment & Correlation")
    st.markdown(
        f"Visualizing the overlapping price action of **{asset_a}** and **{asset_b}** over the backtest duration. "
        "Prices are normalized to a starting value of 100 to show relative percentage moves."
    )
    
    if df_pair.empty or len(df_pair) < 2:
        st.warning("Not enough data to render alignment chart.")
        return

    # Normalize to 100
    df_norm = pd.DataFrame(index=df_pair.index)
    df_norm[asset_a] = (df_pair[asset_a] / df_pair[asset_a].iloc[0]) * 100
    df_norm[asset_b] = (df_pair[asset_b] / df_pair[asset_b].iloc[0]) * 100

    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df_norm.index, 
        y=df_norm[asset_a],
        mode='lines',
        name=asset_a,
        line=dict(width=2, color='#2962FF') # Blue
    ))
    
    fig.add_trace(go.Scatter(
        x=df_norm.index, 
        y=df_norm[asset_b],
        mode='lines',
        name=asset_b,
        line=dict(width=2, color='#FF6D00') # Orange
    ))
    
    fig.update_layout(
        title="Normalized Price History (Base = 100)",
        xaxis_title="Date",
        yaxis_title="Normalized Price",
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)
