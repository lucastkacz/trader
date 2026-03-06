import streamlit as st
import pandas as pd
from src.dashboard.styles import apply_compact_styles
from src.data.universe import UniverseManager
from src.engine.data.loader import DataLoader
from src.data.basket import BasketManager
from src.engine.data.loader import DataLoader
from src.strategies.factory import StrategyFactory
from src.strategies.factory import StrategyFactory

def render_research_page():
    # Apply shared styles
    apply_compact_styles()

    st.title("Alpha Discovery Pipeline")
    st.markdown("Test specific quantitative strategies against a pre-screened Correlated Basket.")

    # 1. Basket Selection
    st.write("### Data Selection")
    
    baskets = BasketManager.list_baskets()
    # Filter for baskets that might be from the correlation step (or just show all for now)
    if not baskets:
        st.warning("No baskets found. Please create one in the Correlation Analysis page.")
        return

    basket_names = [b.get("name", "Unknown") for b in baskets]
    
    col_b1, col_b2 = st.columns([1, 2])
    with col_b1:
        selected_b_name = st.selectbox("Select Input Basket", basket_names)
    
    selected_basket = next((b for b in baskets if b.get("name") == selected_b_name), None)
    
    timeframe = "1h" # Default
    if selected_basket:
        timeframe = selected_basket.get('timeframe', '1h')
        pairs = selected_basket.get('pairs', [])
        
        # We need to extract the unique symbols from the basket pairs to load data
        symbols = set()
        for p in pairs:
            if 'asset_a' in p: symbols.add(p['asset_a'])
            if 'asset_b' in p: symbols.add(p['asset_b'])
            
        with col_b2:
            st.write("") 
            st.write("")
            st.markdown(f"**Pairs to Test:** {len(pairs)} &nbsp;&nbsp;|&nbsp;&nbsp; **Timeframe:** {timeframe}")
        
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
    
    with st.expander("🎓 Strategy Parameters Help", expanded=False):
        st.markdown("""
        Configure the parameters for the specific strategy you are testing.
        *   **Rolling Window:** Generally should match your target Holding Period.
        *   **Max Allowable Metric:** The threshold for the strategy's screening metric (e.g. Cointegration P-Value <= 0.05).
        """)
    
    col1, col2 = st.columns(2)
    with col1:
        strategy_names = list(StrategyFactory.STRATEGY_REGISTRY.keys())
        selected_strategy = st.selectbox("Select Strategy Matrix", strategy_names)

    with col2:
        coint_window = st.number_input("Rolling Window (Periods)", min_value=30, value=168, help="Matches your target holding period.")
        st.caption(f"⏱️ Evaluating over rolling **{get_time_estimate(coint_window, timeframe)}** blocks")
        pval_thresh = st.number_input("Screening Threshold (e.g. Max P-Value)", min_value=0.01, max_value=0.20, value=0.05, step=0.01)

    st.divider()

    # Session State Management
    if 'alpha_results' not in st.session_state:
        st.session_state.alpha_results = None
        # 3. Execution: Strategy Screening
        if st.button("🔬 Run Strategy Screener", type="primary", use_container_width=True):
            if not selected_basket or not symbols:
                st.error("Invalid Basket.")
                return
                
            with st.spinner(f"Running strategy evaluation across candidate pairs..."):
                try:
                    loader = DataLoader(list(symbols), timeframe)
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
                    
                    for idx, pair in enumerate(pairs):
                        asset_a = pair.get('asset_a')
                        asset_b = pair.get('asset_b')
                        correlation = pair.get('correlation', 0.0)
                        
                        metric, metadata = strategy.get_screening_metric(close_df, asset_a, asset_b)
                        
                        if metric is not None:
                            result_row = {
                                'asset_a': asset_a,
                                'asset_b': asset_b,
                                'correlation': correlation,
                                'screening_metric': metric,
                                'strategy_name': selected_strategy
                            }
                            # Merge in strategy-specific metadata (like hedge_ratio)
                            result_row.update(metadata)
                            results_list.append(result_row)
                                
                        progress_bar.progress((idx + 1) / len(pairs))
                        
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
                basket_name = st.text_input("Basket Name", value=f"Strategy_{selected_b_name}_{coint_window}w")
            with col_btn:
                st.write("") # Spacing
                st.write("")
                if st.button("💾 Save Basket", use_container_width=True):
                    if basket_name:
                        saved_path = BasketManager.save_basket(
                            name=basket_name,
                            pairs=results_list,
                            universe_name=selected_basket.get('universe_name', 'Unknown'),
                            timeframe=timeframe,
                            corr_lookback=selected_basket.get('corr_lookback'),
                            coint_window=coint_window,
                            start_date=st.session_state.get('alpha_start_date', ''),
                            end_date=st.session_state.get('alpha_end_date', '')
                        )
                        st.success(f"Basket saved successfully! You can now use this in the Strategy Lab.")
                    else:
                        st.warning("Please provide a name for the basket.")
