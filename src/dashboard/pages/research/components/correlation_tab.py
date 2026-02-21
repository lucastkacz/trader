import streamlit as st
import pandas as pd
import plotly.express as px
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
    
    # UI Controls
    col1, col2 = st.columns(2)
    with col1:
        method = st.selectbox("Correlation Method", ["pearson", "kendall", "spearman"])
    with col2:
        top_n = st.number_input("Show Top N Pairs", min_value=1, max_value=50, value=10)
        
    if st.button("Calculate Correlation Matrix"):
        with st.spinner("Loading data and calculating matrix..."):
            try:
                # 1. Load Data
                loader = DataLoader(symbols, timeframe)
                close_df, _, _ = loader.load() # We only need prices for correlation
                
                if close_df.empty:
                    st.error("No data could be loaded for these symbols. Has data been downloaded?")
                    return
                    
                # 2. Calculate Correlation
                corr_matrix = calculate_correlation_matrix(close_df, method=method)
                
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
                st.plotly_chart(fig, use_container_width=True)
                
            except Exception as e:
                st.error(f"Error during calculation: {e}")
