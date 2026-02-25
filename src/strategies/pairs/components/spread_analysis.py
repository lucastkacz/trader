import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from src.stats.cointegration import calculate_rolling_spread, test_rolling_cointegration

def render_spread_analysis(df_pair: pd.DataFrame, asset_a: str, asset_b: str, window: int):
    """
    Renders Module 2: The Spread & Regime Filter.
    Calculates and visualizes the rolling spread along with the P-Value history 
    used to switch the strategy ON and OFF.
    """
    st.write("### ⚖️ Module 2: The Spread & Regime Filter")
    st.markdown(
        f"This visualizes the raw spread between {asset_a} and {asset_b}. "
        "The bottom chart plots the **Rolling P-Value**. When the P-Value drops below 0.05 (green), "
        "the mathematical relationship is proven, and the strategy is allowed to trade. "
        "When it spikes above 0.05 (red), the relationship has broken down, and the strategy is forced to wait."
    )
    
    if df_pair.empty or len(df_pair) < window:
        st.warning(f"Not enough data to calculate a {window}-period rolling spread.")
        return

    with st.spinner("Calculating Rolling Cointegration Regime..."):
        spread, rolling_beta = calculate_rolling_spread(df_pair[asset_a], df_pair[asset_b], window=window)
        _, p_values = test_rolling_cointegration(df_pair[asset_a], df_pair[asset_b], window=window)

    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.1,
        row_heights=[0.7, 0.3],
        subplot_titles=("Raw Spread", "Rolling P-Value (Cointegration Regime Filter)")
    )
    
    # 1. Spread Plot
    fig.add_trace(
        go.Scatter(
            x=spread.index, 
            y=spread, 
            name="Spread", 
            line=dict(color='#ab47bc') # Purple
        ),
        row=1, col=1
    )
    
    # apply smoothing algorithm
    pval_smoothing_window = 12
    smoothed_p_values = p_values.rolling(window=pval_smoothing_window).mean()
    
    # 2. P-Value Plot (Color Coded with Hysteresis Zones)
    # Green: Safe Entry (<= 0.10)
    # Yellow: Hold Zone (0.10 - 0.40)
    # Red: Cut-off Broken (> 0.40)
    colors = []
    for p in smoothed_p_values:
        if pd.isna(p):
            colors.append('#333333') # Gray out warm-up period
        elif p <= 0.10:
            colors.append('#00E676') # Green
        elif p <= 0.40:
            colors.append('#FFEB3B') # Yellow
        else:
            colors.append('#FF1744') # Red
            
    fig.add_trace(
        go.Bar(
            x=smoothed_p_values.index,
            y=smoothed_p_values,
            name="Smoothed P-Value",
            marker_color=colors,
            marker_line_width=0
        ),
        row=2, col=1
    )
    
    # Add the 0.10 Entry threshold line
    fig.add_hline(
        y=0.10, 
        line_dash="dash", 
        line_color="#00E676", 
        annotation_text="0.10 Entry Barrier", 
        annotation_position="top left",
        row=2, col=1
    )
    
    # Add the 0.40 Cut-off threshold line
    fig.add_hline(
        y=0.40, 
        line_dash="dash", 
        line_color="#FF1744", 
        annotation_text="0.40 Emergency Cut-Off", 
        annotation_position="top left",
        row=2, col=1
    )
    
    # Restrict Y-axis for P-value to make it readable
    fig.update_yaxes(range=[0, min(1.0, smoothed_p_values.max() * 1.1 if not smoothed_p_values.empty else 1.0)], row=2, col=1)

    fig.update_layout(
        height=600,
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=40, r=40, t=40, b=40),
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    return spread, p_values, rolling_beta
