import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from src.stats.cointegration import calculate_rolling_spread, test_rolling_cointegration

def render_spread_analysis(df_pair: pd.DataFrame, asset_a: str, asset_b: str, window: int, coint_entry: float = 0.10, coint_cutoff: float = 0.40):
    """
    Renders Module 2: The Spread & Regime Filter.
    Calculates and visualizes the rolling spread along with the P-Value history 
    used to switch the strategy ON and OFF.
    """
    st.write("### ⚖️ Module 2: The Spread & Regime Filter")
    st.markdown(
        f"**Explanation of the Raw Spread:**\n\n"
        f"The formula for the spread is `Spread = {asset_a} - (Hedge Ratio * {asset_b})`. "
        f"If the graph shows a spread of e.g. `$40,000`, it simply means that `{asset_a}` is currently "
        f"`$40,000` more expensive than the equivalent hedged amount of `{asset_b}`. "
        f"This large number is completely normal because it contains the base price difference (the 'Alpha' intercept) "
        f"between the two vastly different assets. What matters for trading is only the *volatility* and mean-reversion of this spread, not its absolute zero value. "
        f"*(Note: The first {window} bars of the chart are hidden as the model warms up).* \n\n"
        "--- \n\n"
        f"The bottom chart plots the **Rolling P-Value**. When the P-Value drops below 0.10 (green), "
        "the mathematical relationship is proven, and the strategy is allowed to trade. "
        "When it spikes above 0.40 (red), the relationship has broken down, and the strategy is forced to liquidate."
    )
    
    if df_pair.empty or len(df_pair) < window:
        st.warning(f"Not enough data to calculate a {window}-period rolling spread.")
        return

    with st.spinner("Calculating Rolling Cointegration Regime..."):
        spread, rolling_beta = calculate_rolling_spread(df_pair[asset_a], df_pair[asset_b], window=window)
        _, p_values = test_rolling_cointegration(df_pair[asset_a], df_pair[asset_b], window=window)

    fig = make_subplots(
        rows=3, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.1,
        row_heights=[0.5, 0.25, 0.25],
        subplot_titles=("Raw Spread", "Rolling Hedge Ratio (Beta)", "Rolling P-Value (Cointegration Regime Filter)")
    )
    
    # 1. Spread Plot
    # Remove Warm-up period for clean plotting
    plot_spread = spread.copy()
    plot_spread.iloc[:window-1] = pd.NA
    
    fig.add_trace(
        go.Scatter(
            x=plot_spread.index, 
            y=plot_spread, 
            name="Spread", 
            line=dict(color='#ab47bc') # Purple
        ),
        row=1, col=1
    )
    
    # 2. Rolling Beta Plot
    plot_beta = rolling_beta.copy()
    plot_beta.iloc[:window-1] = pd.NA
    
    fig.add_trace(
        go.Scatter(
            x=plot_beta.index,
            y=plot_beta,
            name="Hedge Ratio (Beta)",
            line=dict(color='#29B6F6') # Light blue
        ),
        row=2, col=1
    )
    
    # apply smoothing algorithm
    pval_smoothing_window = 12
    numeric_p_values = pd.to_numeric(p_values, errors='coerce')
    smoothed_p_values = numeric_p_values.rolling(window=pval_smoothing_window).mean()
    
    # 2. P-Value Plot (Color Coded with Hysteresis Zones)
    # Green: Safe Entry (<= coint_entry)
    # Yellow: Hold Zone (coint_entry - coint_cutoff)
    # Red: Cut-off Broken (> coint_cutoff)
    colors = []
    for p in smoothed_p_values:
        if pd.isna(p):
            colors.append('#333333') # Gray out warm-up period
        elif p <= coint_entry:
            colors.append('#00E676') # Green
        elif p <= coint_cutoff:
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
        row=3, col=1
    )
    
    # Add the Entry threshold line
    fig.add_hline(
        y=coint_entry, 
        line_dash="dash", 
        line_color="#00E676", 
        annotation_text=f"{coint_entry:.2f} Entry Barrier", 
        annotation_position="top left",
        row=3, col=1
    )
    
    # Add the Cut-off threshold line
    fig.add_hline(
        y=coint_cutoff, 
        line_dash="dash", 
        line_color="#FF1744", 
        annotation_text=f"{coint_cutoff:.2f} Emergency Cut-Off", 
        annotation_position="top left",
        row=3, col=1
    )
    
    # Restrict Y-axis for P-value to make it readable
    fig.update_yaxes(range=[0, min(1.0, smoothed_p_values.max() * 1.1 if not smoothed_p_values.empty else 1.0)], row=3, col=1)

    fig.update_layout(
        height=600,
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=40, r=40, t=40, b=40),
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    return spread, p_values, rolling_beta
