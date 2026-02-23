import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.engine.data.loader import DataLoader
from src.stats.cointegration import calculate_spread
from src.stats.zscore import calculate_z_score

def render_zscore_tab(universe: dict):
    st.write("### Rolling Z-Score & Spread Dynamics")
    
    if 'research_pair_config' not in st.session_state:
        st.warning("Please run a Cointegration test first to select a pair and calculate their Hedge Ratio.")
        return
        
    config = st.session_state['research_pair_config']
    asset_a = config['asset_a']
    asset_b = config['asset_b']
    hedge_ratio = config['hedge_ratio']
    timeframe = universe.get('timeframe', '1h')
    
    if config.get('is_rolling', False):
        st.info(f"**Selected Pair:** {asset_a} & {asset_b}  |  **Hedge Ratio:** Rolling ({config.get('hedge_window')} periods)")
    else:
        st.info(f"**Selected Pair:** {asset_a} & {asset_b}  |  **Hedge Ratio:** Static ({hedge_ratio:.4f})")
    
    # UI Controls
    col1, col2 = st.columns(2)
    with col1:
        window = st.slider("Z-Score Rolling Window", min_value=10, max_value=200, value=30, step=10)
    with col2:
        threshold = st.number_input("Divergence Threshold", min_value=1.0, max_value=4.0, value=2.0, step=0.1)
        
    if st.button("Calculate & Plot"):
        with st.spinner("Loading data and generating Z-Scores..."):
            try:
                loader = DataLoader([asset_a, asset_b], timeframe)
                close_df, _, _ = loader.load()
                
                df_clean = close_df.dropna()
                
                # Math
                is_rolling = config.get('is_rolling', False)
                if is_rolling:
                    hedge_window = config.get('hedge_window', 90)
                    from src.stats.cointegration import calculate_rolling_spread
                    spread, _ = calculate_rolling_spread(df_clean[asset_a], df_clean[asset_b], window=hedge_window)
                    spread = spread.dropna() # Remove NaNs from rolling origin
                else:
                    spread = calculate_spread(df_clean[asset_a], df_clean[asset_b], hedge_ratio)
                    
                z_score = calculate_z_score(spread, window=window)
                
                # Plot Z-Score
                st.write("#### Z-Score Chart")
                fig_z = go.Figure()
                fig_z.add_trace(go.Scatter(x=z_score.index, y=z_score, mode='lines', name='Z-Score'))
                
                # Threshold Lines
                fig_z.add_hline(y=threshold, line_dash="dash", line_color="red", annotation_text=f"Short Spread (+{threshold})")
                fig_z.add_hline(y=-threshold, line_dash="dash", line_color="green", annotation_text=f"Long Spread (-{threshold})")
                fig_z.add_hline(y=0, line_dash="solid", line_color="gray", annotation_text="Mean (Exit)")
                
                fig_z.update_layout(title="Rolling Z-Score over Time", xaxis_title="Date", yaxis_title="Standard Deviations")
                st.plotly_chart(fig_z, use_container_width=True)
                
                # Plot Raw Spread against Moving Average
                st.write("#### Raw Spread")
                rolling_mean = spread.rolling(window=window).mean()
                
                fig_spread = go.Figure()
                fig_spread.add_trace(go.Scatter(x=spread.index, y=spread, mode='lines', name='Spread'))
                fig_spread.add_trace(go.Scatter(x=rolling_mean.index, y=rolling_mean, mode='lines', name=f'{window}-period Mean', line=dict(dash='dash')))
                
                fig_spread.update_layout(title="Spread Value vs. Average", xaxis_title="Date", yaxis_title="Spread Price")
                st.plotly_chart(fig_spread, use_container_width=True)
                
            except Exception as e:
                st.error(f"Error rendering chart: {e}")
