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

    # Let user select two assets to test
    col1, col2, col3 = st.columns(3)
    with col1:
        asset_a = st.selectbox("Asset A (Dependent, Y)", symbols)
    with col2:
        asset_b = st.selectbox("Asset B (Independent, X)", [s for s in symbols if s != asset_a])
    with col3:
        rolling_window = st.slider("Cointegration Lookback Window", min_value=30, max_value=500, value=90, step=10)
        st.caption(f"⏱️ Estimated Time: **{get_time_estimate(rolling_window, timeframe)}**")
        
    st.info("Equation: `Asset A = Rolling Hedge Ratio * Asset B`")
    
    if st.button("Run Rolling Cointegration Test"):
        with st.spinner("Loading data and running rolling ADF tests (this may take a moment)..."):
            try:
                # Load only the two selected assets to save memory
                loader = DataLoader([asset_a, asset_b], timeframe)
                close_df, _, _ = loader.load()
                
                # Check for NaNs that would break math
                df_clean = close_df.dropna()
                
                if len(df_clean) < rolling_window + 20:
                    st.error(f"Not enough overlapping data between {asset_a} and {asset_b} to test cointegration with window {rolling_window}.")
                    return
                
                from src.stats.cointegration import test_rolling_cointegration, calculate_rolling_spread
                import plotly.graph_objects as go
                
                rolling_adf, rolling_pval = test_rolling_cointegration(df_clean[asset_a], df_clean[asset_b], window=rolling_window)
                _, rolling_beta = calculate_rolling_spread(df_clean[asset_a], df_clean[asset_b], window=rolling_window)
                
                # Get the most recent valid values
                latest_pval = rolling_pval.dropna().iloc[-1]
                latest_adf = rolling_adf.dropna().iloc[-1]
                latest_beta = rolling_beta.dropna().iloc[-1]
                
                st.write("#### Latest Test Results")
                
                # Metrics layout
                m1, m2, m3 = st.columns(3)
                m1.metric("Current Hedge Ratio (β)", f"{latest_beta:.4f}")
                m2.metric("Current ADF Stat", f"{latest_adf:.4f}")
                
                # Color code P-Value based on significance
                p_val_str = f"{latest_pval:.4f}"
                if latest_pval <= 0.05:
                    m3.metric("Current P-Value", p_val_str, "Significant (Stationary)")
                    st.success(f"**Currently Cointegrated!** The spread is recently mean-reverting (p < 0.05).")
                else:
                    m3.metric("Current P-Value", p_val_str, "-Not Significant", delta_color="inverse")
                    st.warning(f"**Not Cointegrated.** The spread is currently not reliably reverting to a mean (p > 0.05).")
                
                # Animated Plot P-Values
                st.write("#### Animated P-Value Evolution by Window Size")
                st.info("Press Play to watch how the P-Value curve changes across different lookback window sizes.")
                
                # We need to run the cointegration test across multiple window sizes
                max_window = rolling_window
                windows_to_test = list(range(30, max_window + 1, 10))
                if rolling_window not in windows_to_test:
                    windows_to_test.append(rolling_window)
                    
                # To prevent completely freezing the app, we limit the number of frames
                if len(windows_to_test) > 20:
                    step = max(10, (max_window - 30) // 20)
                    windows_to_test = list(range(30, max_window + 1, step))
                    if rolling_window not in windows_to_test:
                        windows_to_test.append(rolling_window)
                
                anim_df_list = []
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                global_min_date = df_clean.index[0]
                global_max_date = df_clean.index[-1]
                
                # Collect valid pval max for Y-axis scaling
                global_max_pval = 0.2
                
                for idx, w in enumerate(windows_to_test):
                    status_text.text(f"Calculating rolling P-Values for window size {w}... ({idx+1}/{len(windows_to_test)})")
                    
                    # We only care about P-value for the animation
                    _, w_pval = test_rolling_cointegration(df_clean[asset_a], df_clean[asset_b], window=w)
                    valid_w_pval = w_pval.dropna()
                    
                    if len(valid_w_pval) > 0:
                        temp_df = pd.DataFrame({
                            'Date': valid_w_pval.index,
                            'P-Value': valid_w_pval.values,
                            'Frame': f"Window: {w}"
                        })
                        anim_df_list.append(temp_df)
                        current_max = valid_w_pval.max()
                        if current_max > global_max_pval:
                            global_max_pval = current_max
                            
                    progress_bar.progress((idx + 1) / len(windows_to_test))
                    
                status_text.empty()
                progress_bar.empty()
                
                if anim_df_list:
                    anim_df = pd.concat(anim_df_list)
                    
                    import plotly.express as px
                    
                    fig_pval = px.line(anim_df, x="Date", y="P-Value", animation_frame="Frame", 
                                     range_y=[0, min(1.05, global_max_pval * 1.1)],
                                     range_x=[global_min_date, global_max_date])
                                     
                    fig_pval.add_hline(y=0.05, line_dash="dash", line_color="red", annotation_text="Significance (0.05)")
                    fig_pval.update_layout(yaxis_title="P-Value", height=400)
                    
                    # Set a smooth animation speed for stepping through window sizes
                    fig_pval.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 600
                    fig_pval.layout.updatemenus[0].buttons[0].args[1]["transition"]["duration"] = 300
                    
                    st.plotly_chart(fig_pval, use_container_width=True)
                else:
                    st.warning("Not enough valid calculations to animate.")
                
                # Plot Beta
                st.write("#### Rolling Hedge Ratio (β) Over Time")
                fig_beta = go.Figure()
                fig_beta.add_trace(go.Scatter(x=rolling_beta.index, y=rolling_beta, mode='lines', name='Hedge Ratio', line=dict(color='orange')))
                fig_beta.update_layout(yaxis_title="Hedge Ratio (Units of B per A)", xaxis_title="Date", height=300)
                st.plotly_chart(fig_beta, use_container_width=True)
                
                # Save configuration explicitly marking that we used rolling methods
                st.session_state['research_pair_config'] = {
                    'asset_a': asset_a,
                    'asset_b': asset_b,
                    'is_rolling': True,
                    'hedge_window': rolling_window,
                    'hedge_ratio': latest_beta # Fallback explicitly
                }
                
            except Exception as e:
                st.error(f"Error running cointegration test: {e}")
