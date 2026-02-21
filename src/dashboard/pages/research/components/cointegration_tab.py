import streamlit as st
import pandas as pd
from src.engine.data.loader import DataLoader
from src.stats.cointegration import test_cointegration

def render_cointegration_tab(universe: dict):
    st.write("### Cointegration Analysis (Engle-Granger)")
    
    if not universe or 'symbols' not in universe:
        st.warning("Invalid universe configuration selected.")
        return
        
    symbols = universe['symbols']
    timeframe = universe.get('timeframe', '1h')
    
    # Check if we have top pairs from Correlation tab
    top_pairs_df = st.session_state.get('research_top_pairs', None)
    
    # Let user select two assets to test
    col1, col2 = st.columns(2)
    with col1:
        asset_a = st.selectbox("Asset A (Dependent, Y)", symbols)
    with col2:
        asset_b = st.selectbox("Asset B (Independent, X)", [s for s in symbols if s != asset_a])
        
    st.info("Equation: `Asset A = Hedge Ratio * Asset B`")
    
    if st.button("Run Cointegration Test"):
        with st.spinner("Loading data and running ADF test..."):
            try:
                # Load only the two selected assets to save memory
                loader = DataLoader([asset_a, asset_b], timeframe)
                close_df, _, _ = loader.load()
                
                # Check for NaNs that would break OLS
                df_clean = close_df.dropna()
                
                if len(df_clean) < 30:
                    st.error(f"Not enough overlapping data between {asset_a} and {asset_b} to test cointegration.")
                    return
                    
                beta, adf_stat, p_value = test_cointegration(df_clean[asset_a], df_clean[asset_b])
                
                st.write("#### Test Results")
                
                # Metrics layout
                m1, m2, m3 = st.columns(3)
                m1.metric("Hedge Ratio (β)", f"{beta:.4f}")
                m2.metric("ADF Statistic", f"{adf_stat:.4f}")
                
                # Color code P-Value based on significance
                p_val_str = f"{p_value:.4f}"
                if p_value <= 0.05:
                    m3.metric("P-Value", p_val_str, "Significant (Stationary)")
                    st.success(f"**Cointegrated!** The spread between {asset_a} and {asset_b} is mean-reverting (p < 0.05).")
                else:
                    m3.metric("P-Value", p_val_str, "-Not Significant", delta_color="inverse")
                    st.warning(f"**Not Cointegrated.** The spread does not reliably revert to a mean (p > 0.05).")
                
                # Save Hedge ratio to session state so next tab can use it
                st.session_state['research_pair_config'] = {
                    'asset_a': asset_a,
                    'asset_b': asset_b,
                    'hedge_ratio': beta
                }
                
            except Exception as e:
                st.error(f"Error running cointegration test: {e}")
