import streamlit as st
import pandas as pd
from src.dashboard.styles import apply_compact_styles
from src.data.universe import UniverseManager
from src.engine.data.loader import DataLoader
from src.stats.correlation import calculate_correlation_matrix, get_top_correlated_pairs
from src.data.basket import BasketManager
from src.strategies.factory import StrategyFactory

def render_research_page():
    # Apply shared styles
    apply_compact_styles()

    st.title("Alpha Discovery Pipeline")
    st.markdown("Statistically prove mean-reverting relationships (Cointegration) and save them as Baskets.")

    # 1. Universe Selection
    st.write("### Data Selection")
    
    universes = UniverseManager.list_universes()
    if not universes:
        st.warning("No universes found. Please create one in Data Management.")
        return

    universe_names = [u.get("name", "Unknown") for u in universes]
    
    col_u1, col_u2 = st.columns([1, 2])
    with col_u1:
        selected_u_name = st.selectbox("Select Universe", universe_names)
    
    selected_universe = next((u for u in universes if u.get("name") == selected_u_name), None)
    
    timeframe = "1h" # Default
    if selected_universe:
        timeframe = selected_universe.get('timeframe', '1h')
        with col_u2:
            st.write("") # Add spacing to align with selectbox
            st.write("")
            st.markdown(f"**Symbols:** {len(selected_universe.get('symbols', []))} &nbsp;&nbsp;|&nbsp;&nbsp; **Timeframe:** {timeframe}")
        
    st.divider()
    
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
    
    # 2. Screener Parameters
    st.write("### Discovery Parameters")
    
    with st.expander("🎓 How to choose your parameters (Read Me First)", expanded=False):
        st.markdown("""
        There is no "magic number" for these parameters. They depend entirely on your **Holding Period**.
        
        **Step 1: Determine Your Target Holding Period**
        *   *Day Trader:* You want to enter and exit a trade within hours.
        *   *Swing Trader:* You want to hold a trade for 1 to 2 weeks.
        
        **Step 2: Set Cointegration Stability (The Precise Math)**
        Your Cointegration Window should roughly equal your intended Holding Period.
        *   *Why?* If you want to hold a trade for 1 week, you need to prove the assets snap back together within a 1-week timeframe. 
        *   *Example (1h Universe):* To hold for 1 week (7 days), set the Rolling Window to **168**. 
        
        **Step 3: Set Correlation Filter (The Big Picture)**
        Your Correlation Lookback should be **3 to 4 times larger** than your Cointegration Window.
        *   *Why?* You want to know if these assets have a *long-term history* of moving together, not just a lucky week.
        *   *Example:* If your Cointegration Window is 168, set the Correlation Lookback to **672** (about 1 month).
        """)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**1. Correlation Filter (Long-Term)**")
        corr_lookback = st.number_input("Lookback (Periods)", min_value=30, value=672, help="Rule of Thumb: This should be 3-4x larger than your Cointegration Window.")
        st.caption(f"⏱️ Analyzing deep history over the last **{get_time_estimate(corr_lookback, timeframe)}**")
        top_n = st.number_input("Test Top N Pairs", min_value=1, value=15, help="How many highly correlated pairs to pass to Step 2")
        
    with col2:
        st.markdown("**2. Strategy Selection & Screening**")
        strategy_names = list(StrategyFactory.STRATEGY_REGISTRY.keys())
        selected_strategy = st.selectbox("Select Strategy Matrix", strategy_names)

        coint_window = st.number_input("Rolling Window (Periods)", min_value=30, value=168, help="Rule of Thumb: This should match your target Trade Holding Period.")
        st.caption(f"⏱️ Evaluating over rolling **{get_time_estimate(coint_window, timeframe)}** blocks")
        pval_thresh = st.number_input("Max Allowable Metric (e.g. P-Value)", min_value=0.01, max_value=0.20, value=0.05, step=0.01)

    st.divider()

    # Session State Management
    if 'alpha_results' not in st.session_state:
        st.session_state.alpha_results = None
    if 'alpha_candidates' not in st.session_state:
        st.session_state.alpha_candidates = None
    if 'alpha_corr_matrix' not in st.session_state:
        st.session_state.alpha_corr_matrix = None

    # 3. Execution Step A: Correlation
    if st.button("📊 Step 1: Run Correlation Filter", use_container_width=True):
        if not selected_universe or 'symbols' not in selected_universe:
            st.error("Invalid Universe.")
            return
            
        symbols = selected_universe['symbols']
        
        with st.spinner(f"Loading {get_time_estimate(corr_lookback, timeframe)} of data and building heatmaps..."):
            try:
                # Load Data
                loader = DataLoader(symbols, timeframe)
                close_df, _, _ = loader.load()
                
                if close_df.empty:
                    st.error("No data found.")
                    return
                    
                recent_df = close_df.tail(corr_lookback)
                st.session_state.alpha_corr_matrix = calculate_correlation_matrix(recent_df, method='pearson')
                st.session_state.alpha_candidates = get_top_correlated_pairs(st.session_state.alpha_corr_matrix, top_n=top_n)
                # Reset downstream step if re-running step 1
                st.session_state.alpha_results = None 
                
            except Exception as e:
                st.error(f"Correlation check failed: {str(e)}")

    import plotly.express as px

    if st.session_state.alpha_corr_matrix is not None and st.session_state.alpha_candidates is not None:
        st.write("### Step 1 Results: Correlation Matrix")
        st.info("Visual validation of asset relationships over the selected lookback.")
        
        fig = px.imshow(
            st.session_state.alpha_corr_matrix, 
            color_continuous_scale="RdBu_r", 
            zmin=-1, zmax=1,
            aspect="auto"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.write(f"**Top {len(st.session_state.alpha_candidates)} Candidates Selected for Cointegration:**")
        st.dataframe(
            st.session_state.alpha_candidates.style.format({'Correlation': "{:.2f}"}),
            use_container_width=True
        )

        st.divider()
        
        # 4. Execution Step B: Strategy Screening
        if st.button("🔬 Step 2: Run Strategy Screener", type="primary", use_container_width=True):
            symbols = selected_universe['symbols']
            top_pairs_df = st.session_state.alpha_candidates
            
            with st.spinner(f"Running strategy evaluation across {len(top_pairs_df)} candidate pairs..."):
                try:
                    loader = DataLoader(symbols, timeframe)
                    close_df, _, _ = loader.load()
                    
                    results_list = []
                    progress_bar = st.progress(0)
                    
                    # Instantiate strategy dynamically
                    config = {
                        "name": selected_strategy,
                        "timeframe": timeframe,
                        "parameters": {
                            "cointegration_window": coint_window,
                            "cointegration_thresholds": {"entry": pval_thresh, "cutoff": pval_thresh * 4}
                        }
                    }
                    strategy = StrategyFactory.create(config)
                    sort_ascending = strategy.sort_ascending
                    
                    for idx, row in top_pairs_df.iterrows():
                        asset_a = row['Asset_1']
                        asset_b = row['Asset_2']
                        
                        metric, metadata = strategy.get_screening_metric(close_df, asset_a, asset_b)
                        
                        if metric is not None:
                            result_row = {
                                'asset_a': asset_a,
                                'asset_b': asset_b,
                                'correlation': row['Correlation'],
                                'screening_metric': metric,
                                'strategy_name': selected_strategy
                            }
                            # Merge in strategy-specific metadata (like hedge_ratio)
                            result_row.update(metadata)
                            results_list.append(result_row)
                                
                        progress_bar.progress((idx + 1) / len(top_pairs_df))
                        
                    progress_bar.empty()
                    st.session_state.alpha_results = results_list
                    st.session_state.alpha_sort_ascending = sort_ascending
                    st.session_state.alpha_start_date = str(close_df.index[0].date()) if not close_df.empty else ""
                    st.session_state.alpha_end_date = str(close_df.index[-1].date()) if not close_df.empty else ""
                    
                except Exception as e:
                    st.error(f"Cointegration testing failed: {str(e)}")

    # 5. Display Final Results and Save Basket Form
    if st.session_state.alpha_results is not None:
        results_list = st.session_state.alpha_results
        
        if not results_list:
            st.warning("No pairs survived the Strategy Screening filter.")
        else:
            results_df = pd.DataFrame(results_list)
            
            # Sort by strategy preference
            sort_ascending = st.session_state.get('alpha_sort_ascending', True)
            results_df = results_df.sort_values('screening_metric', ascending=sort_ascending)
            
            st.success(f"Discovery Complete! {len(results_df)} Pairs share a proven statistical relationship.")
            
            st.write("### Alpha Discovery Results (Ranked by Strategy Metric)")
            
            # Determine which columns to show (dynamic based on metadata)
            display_cols = ['asset_a', 'asset_b', 'correlation', 'screening_metric']
            format_dict = {'correlation': "{:.2f}", 'screening_metric': "{:.4f}"}
            
            if 'hedge_ratio' in results_df.columns:
                display_cols.append('hedge_ratio')
                format_dict['hedge_ratio'] = "{:.4f}"
                
            st.dataframe(
                results_df[display_cols].style.format(format_dict),
                use_container_width=True
            )
            
            # Save Basket Form
            st.divider()
            st.write("### Build Strategy Basket")
            st.info("Save these proven pairs into a Basket to be used in the Strategy Lab for execution backtesting.")
            
            col_name, col_btn = st.columns([3, 1])
            with col_name:
                basket_name = st.text_input("Basket Name", value=f"Alpha_{selected_u_name}_{coint_window}w")
            with col_btn:
                st.write("") # Spacing
                st.write("")
                if st.button("💾 Save Basket", use_container_width=True):
                    if basket_name:
                        saved_path = BasketManager.save_basket(
                            name=basket_name,
                            pairs=results_list,
                            universe_name=selected_u_name,
                            timeframe=timeframe,
                            corr_lookback=corr_lookback,
                            coint_window=coint_window,
                            start_date=st.session_state.get('alpha_start_date', ''),
                            end_date=st.session_state.get('alpha_end_date', '')
                        )
                        st.success(f"Basket saved successfully! You can now use this in the Strategy Lab.")
                    else:
                        st.warning("Please provide a name for the basket.")
