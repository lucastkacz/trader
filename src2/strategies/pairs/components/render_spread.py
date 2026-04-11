import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from src.stats.cointegration import calculate_rolling_spread, test_rolling_cointegration

def plot_spread_and_regime(df_pair: pd.DataFrame, asset_a: str, asset_b: str, coint_window: int, coint_entry: float, coint_cutoff: float):
    """
    Renders Phase 2: Spread Calculation & Regime Filter.
    Calculates the rolling spread using OLS and evaluates the ADF P-Value
    to determine the current Cointegration regime.
    """
    if df_pair.empty or len(df_pair) < coint_window:
        st.warning(f"Not enough data to calculate a {coint_window}-period rolling spread.")
        return None, None, None
        
    st.markdown(
        f"We now run a statistically sound **Rolling Ordinary Least Squares (OLS) Regression** over a `{coint_window}` bar window. "
        f"This calculates a dynamic Hedge Ratio (`Beta`) to ensure we are comparing Apples to Apples, rather than raw price dollars. "
    )
    
    with st.spinner("Calculating Rolling Spread and ADF Cointegration..."):
        spread, rolling_beta = calculate_rolling_spread(df_pair[asset_a], df_pair[asset_b], window=coint_window)
        _, p_values = test_rolling_cointegration(df_pair[asset_a], df_pair[asset_b], window=coint_window)

    fig = make_subplots(
        rows=3, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.1,
        row_heights=[0.5, 0.25, 0.25],
        subplot_titles=("Raw Spread (Residuals)", "Rolling Hedge Ratio (OLS Beta)", "Cointegration Regime Filter (Smoothed P-Value)")
    )
    
    # 1. Spread Plot
    plot_spread = spread.copy()
    plot_spread.iloc[:coint_window-1] = pd.NA
    
    fig.add_trace(
        go.Scatter(
            x=plot_spread.index, 
            y=plot_spread, 
            name="Spread", 
            line=dict(color='#ab47bc', width=1) # Purple
        ),
        row=1, col=1
    )
    
    # 2. Rolling Beta Plot
    plot_beta = rolling_beta.copy()
    plot_beta.iloc[:coint_window-1] = pd.NA
    
    fig.add_trace(
        go.Scatter(
            x=plot_beta.index,
            y=plot_beta,
            name="Hedge Ratio (Beta)",
            line=dict(color='#29B6F6', width=2) # Light blue
        ),
        row=2, col=1
    )
    
    # 3. P-Value Plot (Color Coded with Hysteresis Zones)
    pval_smoothing_window = 12
    numeric_p_values = pd.to_numeric(p_values, errors='coerce')
    smoothed_p_values = numeric_p_values.rolling(window=pval_smoothing_window).mean()
    
    colors = []
    for p in smoothed_p_values:
        if pd.isna(p):
            colors.append('#333333') # Gray out warm-up period
        elif p <= coint_entry:
            colors.append('#00E676') # Green (Valid Regime)
        elif p <= coint_cutoff:
            colors.append('#FFEB3B') # Yellow (Holding Zone)
        else:
            colors.append('#FF1744') # Red (Broken Regime)
            
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
    
    # Add thresholds
    fig.add_hline(
        y=coint_entry, line_dash="dash", line_color="#00E676", 
        annotation_text=f"Entry ({coint_entry:.2f})", annotation_position="top left", row=3, col=1
    )
    fig.add_hline(
        y=coint_cutoff, line_dash="dash", line_color="#FF1744", 
        annotation_text=f"Cut-Off ({coint_cutoff:.2f})", annotation_position="top left", row=3, col=1
    )
    
    fig.update_yaxes(range=[0, min(1.0, smoothed_p_values.max() * 1.1 if not smoothed_p_values.empty else 1.0)], row=3, col=1)

    fig.update_layout(
        height=650,
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=40, r=40, t=60, b=40),
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    return spread, smoothed_p_values, rolling_beta
