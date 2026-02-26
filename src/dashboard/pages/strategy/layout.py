import streamlit as st
import pandas as pd
from src.dashboard.styles import apply_compact_styles
from src.data.basket import BasketManager
from src.engine.data.loader import DataLoader

# Import modular components
from src.strategies.pairs.components.data_alignment import render_data_alignment
from src.strategies.pairs.components.spread_analysis import render_spread_analysis
from src.strategies.pairs.components.signal_gen import render_signal_gen
from src.strategies.pairs.components.execution import render_execution
from src.strategies.pairs.logic import PairsTradingStrategy

def render_strategy_page():
    apply_compact_styles()

    st.title("Strategy Lab (Deep Inspection)")
    st.markdown("Select a proven Alpha Basket, then pick **one pair** to step through the mathematical execution pipeline visually.")
    
    # 0. Strategy Documentation
    import os
    readme_path = os.path.join("src", "strategies", "pairs", "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, "r") as f:
            readme_content = f.read()
        with st.expander("📖 Strategy Documentation & Rules", expanded=False):
            st.markdown(readme_content)

    # 1. Selection Header
    col_b, col_p = st.columns(2)
    baskets = BasketManager.list_baskets()
    
    if not baskets:
        st.warning("No Baskets found. Please run Alpha Discovery and save a basket first.")
        return
        
    basket_names = [b.get("name", "Unknown") for b in baskets]
    
    with col_b:
        selected_b_name = st.selectbox("1. Select Alpha Basket", basket_names)
    
    selected_basket = next((b for b in baskets if b.get("name") == selected_b_name), None)
    
    if not selected_basket or not selected_basket.get('pairs'):
        st.warning("Empty basket.")
        return

    pairs = selected_basket['pairs']
    timeframe = selected_basket.get('timeframe', '1h')
    coint_window = selected_basket.get('metadata', {}).get('cointegration_window_periods', 168)
    
    # 2. Pair Selection
    pair_strs = [f"{p['asset_a']} / {p['asset_b']} (Corr: {p.get('correlation', 0):.2f})" for p in pairs]
    
    with col_p:
        selected_pair_str = st.selectbox("2. Select Pair to Inspect", pair_strs)
        
    selected_pair_idx = pair_strs.index(selected_pair_str)
    p = pairs[selected_pair_idx]
    asset_a = p['asset_a']
    asset_b = p['asset_b']

    st.divider()

    # 3. Strategy Parameters (Global Header)
    with st.expander("⚙️ Execution Parameters (Z-Score & Portfolio)", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            coint_window_input = st.number_input(
                "Cointegration Window", 
                min_value=10, 
                value=int(coint_window)
            )
            coint_entry = st.number_input("P-Value Entry Barrier", min_value=0.01, max_value=1.0, value=0.10, step=0.01)
            coint_cutoff = st.number_input("P-Value Emergency Cutoff", min_value=0.05, max_value=1.0, value=0.40, step=0.01)
        with c2:
            z_window = st.number_input("Z-Score Moving Average", min_value=10, value=30)
            z_entry = st.number_input("Z-Score Entry", min_value=1.0, value=2.0, step=0.1)
            z_exit = st.number_input("Z-Score Exit", min_value=-1.0, value=0.0, step=0.1)
        with c3:
            capital_per_pair = st.number_input("Capital Allocation ($)", min_value=1000.0, value=10000.0, step=1000.0)
            fee_rate = st.number_input("Exchange Fee Rate (%)", min_value=0.0, value=0.05, step=0.01) / 100.0
            slippage = st.number_input("Slippage (%)", min_value=0.0, value=0.02, step=0.01) / 100.0

    st.divider()

    # 4. Global Data Fetching (Passes down to modules)
    with st.spinner(f"Loading deep historical data for {asset_a} and {asset_b} ({timeframe})..."):
        try:
            loader = DataLoader([asset_a, asset_b], timeframe)
            close_df, _, _ = loader.load()
            df_pair = close_df[[asset_a, asset_b]].ffill().dropna()
            
            # Fetch Raw OHLC for execution charts
            raw_a = loader.data_dict.get(asset_a)
            raw_b = loader.data_dict.get(asset_b)
        except Exception as e:
            st.error(f"Failed to load market data: {e}")
            return
            
    if df_pair.empty:
        st.error("Data missing for these assets.")
        return

    # --- PIPELINE RENDERING ---
    
    # Module 1
    render_data_alignment(df_pair, asset_a, asset_b)
    st.divider()
    
    # Module 2
    spread, p_values, rolling_beta = render_spread_analysis(df_pair, asset_a, asset_b, window=coint_window_input, coint_entry=coint_entry, coint_cutoff=coint_cutoff)
    st.divider()
    
    # Module 3
    signals = render_signal_gen(spread, p_values, z_window=z_window, z_entry=z_entry, z_exit=z_exit, coint_entry=coint_entry, coint_cutoff=coint_cutoff)
    if signals is None:
        return
        
    st.divider()
    
    # Run the Engine Logic via the Strategy Class itself
    # This generates the unified metrics and the enriched Trade Log
    strategy = PairsTradingStrategy(
        timeframe=timeframe,
        cointegration_window=coint_window_input,
        cointegration_p_value_threshold=coint_entry,
        cointegration_cutoff_threshold=coint_cutoff,
        zscore_window=z_window,
        entry_threshold=z_entry,
        exit_threshold=z_exit,
        capital_per_pair=capital_per_pair,
        fee_rate=fee_rate,
        slippage=slippage
    )
    
    results = strategy.evaluate_pair(asset_a, asset_b, close_df, basket_name=selected_b_name)
    trade_log = results.get('trade_log', None) if results else None
    report_text = results.get('report_text', None) if results else None
    
    # Module 4
    render_execution(
        df_pair=df_pair, 
        signals=signals, 
        rolling_beta=rolling_beta, 
        asset_a=asset_a, 
        asset_b=asset_b, 
        capital=capital_per_pair, 
        fee_rate=fee_rate, 
        slippage=slippage,
        trade_log=trade_log,
        report_text=report_text,
        basket_name=selected_b_name,
        raw_a=raw_a,
        raw_b=raw_b
    )
    
    st.markdown("<br><br><br>", unsafe_allow_html=True) # Spacer for scrolling
