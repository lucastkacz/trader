import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.engine.data.loader import DataLoader
from src.stats.correlation import calculate_correlation_matrix, get_top_correlated_pairs

def render_correlation_tab(universe: dict):
    st.write("### Rolling Correlation Analysis")
    
    if not universe or 'symbols' not in universe:
        st.warning("Invalid universe configuration selected.")
        return
        
    symbols = universe['symbols']
    timeframe = universe.get('timeframe', '1h')
    
    if not symbols:
        st.warning("Universe contains no symbols.")
        return
        
    st.markdown(f"**Analyzing {len(symbols)} symbols at {timeframe} timeframe.**")
    
    # Timeframe Conversion Helper
    def get_time_estimate(periods: int, tf_str: str) -> str:
        try:
            if tf_str.endswith('m'):
                mins = int(tf_str[:-1]) * periods
                if mins < 60: return f"{mins} minutes"
                hours = mins / 60
                if hours < 24: return f"{hours:.1f} hours"
                return f"{(hours / 24):.2f} days"
            elif tf_str.endswith('h'):
                hours = int(tf_str[:-1]) * periods
                if hours < 24: return f"{hours} hours"
                return f"{(hours / 24):.2f} days"
            elif tf_str.endswith('d'):
                days = int(tf_str[:-1]) * periods
                if days < 30: return f"{days} days"
                return f"{(days / 30):.1f} months"
            return f"{periods} periods"
        except:
            return f"{periods} periods"

    # UI Controls
    col1, col2, col3 = st.columns(3)
    with col1:
        method = st.selectbox("Correlation Method", ["pearson", "kendall", "spearman"])
    with col2:
        top_n = st.number_input("Show Top N Pairs", min_value=1, max_value=50, value=10)
    with col3:
        lookback = st.slider("Lookback Window (Periods)", min_value=30, max_value=1000, value=180, step=30)
        st.caption(f"⏱️ Estimated Time: **{get_time_estimate(lookback, timeframe)}**")
        
    if st.button("Calculate Correlation Matrix"):
        with st.spinner("Loading data and calculating matrix..."):
            try:
                # 1. Load Data
                loader = DataLoader(symbols, timeframe)
                close_df, _, _ = loader.load() # We only need prices for correlation
                
                if close_df.empty:
                    st.error("No data could be loaded for these symbols. Has data been downloaded?")
                    return
                    
                # 2. Slice to the most recent window to capture current regime
                recent_df = close_df.tail(lookback)
                
                if len(recent_df) < 30:
                    st.warning("Not enough data points in the selected lookback window.")
                    
                # 3. Calculate Correlation
                corr_matrix = calculate_correlation_matrix(recent_df, method=method)
                
                # 3. Get Top Pairs
                top_pairs = get_top_correlated_pairs(corr_matrix, top_n=top_n)
                
                # Store in session state for other tabs
                st.session_state['research_top_pairs'] = top_pairs
                
                # 4. Render
                st.success("Calculation complete.")
                
                st.write(f"#### Top {top_n} Correlated Pairs")
                st.dataframe(top_pairs, use_container_width=True)
                
                st.write("#### Correlation Heatmap")
                fig = px.imshow(
                    corr_matrix,
                    text_auto=".2f",
                    aspect="auto",
                    color_continuous_scale="RdBu_r",
                    zmin=-1, zmax=1
                )
                # 5. Plot Historical Rolling Correlation for Top Pairs
                st.write("#### Historical Correlation for Top Pairs")
                st.info(f"How the correlation between the Top {top_n} pairs changed over the last {lookback} periods.")
                
                # Calculate rolling correlation for the top pairs over a smaller internal window (e.g. 1/3 of lookback)
                # To see the line move, we need a smaller rolling window inside the main lookback window
                internal_roll = max(10, int(lookback / 5)) 
                
                fig_hist_corr = go.Figure()
                
                # Iterate top pairs
                for idx, row in top_pairs.iterrows():
                    asset_1 = row['Asset_1']
                    asset_2 = row['Asset_2']
                    
                    # Compute rolling correlation between these two
                    rolling_corr = recent_df[asset_1].rolling(window=internal_roll).corr(recent_df[asset_2])
                    
                    fig_hist_corr.add_trace(go.Scatter(
                        x=rolling_corr.index, 
                        y=rolling_corr, 
                        mode='lines', 
                        name=f"{asset_1} & {asset_2}"
                    ))
                    
                fig_hist_corr.update_layout(
                    yaxis_title="Rolling Correlation", 
                    xaxis_title="Date",
                    height=400,
                    hovermode="x unified"
                )
                st.plotly_chart(fig_hist_corr, use_container_width=True)
                
            except Exception as e:
                st.error(f"Error during calculation: {e}")
