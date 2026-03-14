import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def plot_raw_normalized_prices(df_pair: pd.DataFrame, asset_a: str, asset_b: str):
    """
    Renders Phase 1: Raw Normalized Prices.
    Plots the two assets starting from a base index of 100 to visually compare
    their relative performance and correlation over the selected timeframe.
    """
    if df_pair.empty:
        st.warning(f"No data available to plot for {asset_a} and {asset_b}.")
        return
        
    st.markdown(
        "By normalizing the starting price of both assets to $100$ at the beginning of the selected timeframe, "
        "we can visually inspect if they are moving together (correlated) before calculating the spread."
    )

    # Normalize prices to base 100 for visual comparison
    norm_a = (df_pair[asset_a] / df_pair[asset_a].iloc[0]) * 100
    norm_b = (df_pair[asset_b] / df_pair[asset_b].iloc[0]) * 100

    fig = go.Figure()

    # Asset A
    fig.add_trace(
        go.Scatter(
            x=norm_a.index, 
            y=norm_a, 
            name=asset_a,
            line=dict(color='#00E676', width=2) # Green
        )
    )

    # Asset B
    fig.add_trace(
        go.Scatter(
            x=norm_b.index, 
            y=norm_b, 
            name=asset_b,
            line=dict(color='#29B6F6', width=2) # Blue
        )
    )

    fig.update_layout(
        title=f"Normalized Price Comparison (Base=100)",
        height=500,
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    fig.update_yaxes(title_text="Normalized Price Index")

    st.plotly_chart(fig, use_container_width=True)
