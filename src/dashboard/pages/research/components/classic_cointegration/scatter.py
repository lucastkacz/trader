import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np
from src.dashboard.styles import COLORS

def render_cointegration_scatter(df: pd.DataFrame, asset_a: str, asset_b: str, metric_value: float):
    """
    Renders a scatter plot with an OLS regression line to visualize the 
    linear relationship (cointegration base) between two assets.
    """
    st.write(f"### 📈 Cointegration Visualizer: {asset_a} vs {asset_b}")
    st.markdown(f"**P-Value (Dickey-Fuller):** `{metric_value:.4f}`")
    
    # Calculate simple linear regression for the trendline
    x = df[asset_a].values
    y = df[asset_b].values
    
    # Create the scatter plot using plotly express
    fig = px.scatter(
        df, 
        x=asset_a, 
        y=asset_b,
        opacity=0.6,
        color_discrete_sequence=[COLORS['primary']],
        trendline="ols",
        trendline_color_override=COLORS['secondary']
    )
    
    fig.update_layout(
        plot_bgcolor=COLORS['background'],
        paper_bgcolor=COLORS['background'],
        font_color=COLORS['text'],
        margin=dict(l=40, r=40, t=40, b=40),
        xaxis_title=f"{asset_a} Price",
        yaxis_title=f"{asset_b} Price"
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Extract hedge ratio from OLS results if possible
    results = px.get_trendline_results(fig)
    if not results.empty:
        model = results.iloc[0]["px_fit_results"]
        # Use standard indexing [1] since model.params can be a numpy array
        hedge_ratio = model.params[1] if len(model.params) > 1 else model.params[0]
        r_squared = model.rsquared
        
        st.caption(f"**OLS Hedge Ratio ($\\\\beta$):** `{hedge_ratio:.4f}` | **$R^2$:** `{r_squared:.4f}`")
        st.markdown("*A stable, tight spread around this orange regression line suggests mean-reverting behavior.*")
