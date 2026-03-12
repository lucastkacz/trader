import streamlit as st
import pandas as pd
from src.dashboard.styles import apply_compact_styles
from src.data.basket import BasketManager
from src.engine.data.loader import DataLoader

# Removed modular components for clean slate rebuild
from src.strategies.factory import StrategyFactory

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

    # 1. Strategy Selection
    strategy_options = list(StrategyFactory.STRATEGY_REGISTRY.keys())
    col_s, col_b, col_p = st.columns(3)
    
    with col_s:
        selected_strategy = st.selectbox("1. Select Strategy", strategy_options)

    # 2. Basket Selection (Filtered)
    all_baskets = BasketManager.list_baskets(basket_type="strategy")
    
    # Filter baskets by selected strategy (or fallback for older baskets missing the metadata tag)
    compatible_baskets = []
    for b in all_baskets:
        meta_strat = b.get("metadata", {}).get("strategy_name")
        if meta_strat == selected_strategy or meta_strat is None: # None allows older baskets to still be loaded
            compatible_baskets.append(b)
            
    if not compatible_baskets:
        st.warning(f"No valid Alpha Baskets found for '{selected_strategy}'. Head over to Alpha Discovery to build one first.")
        return
        
    basket_names = [b.get("name", "Unknown") for b in compatible_baskets]
    
    with col_b:
        selected_b_name = st.selectbox("2. Select Alpha Basket", basket_names)
    
    selected_basket = next((b for b in compatible_baskets if b.get("name") == selected_b_name), None)
    
    if not selected_basket or not selected_basket.get('pairs'):
        st.warning("Selected basket is empty.")
        return

    pairs = selected_basket['pairs']
    timeframe = selected_basket.get('timeframe', '1h')
    coint_window_default = selected_basket.get('metadata', {}).get('cointegration_window_periods', 168)
    
    # 3. Pair Selection
    pair_strs = [f"{p['asset_a']} / {p['asset_b']}" for p in pairs]
    
    with col_p:
        selected_pair_str = st.selectbox("3. Select Pair to Inspect", pair_strs)
        
    selected_pair_idx = pair_strs.index(selected_pair_str)
    p = pairs[selected_pair_idx]
    asset_a = p['asset_a']
    asset_b = p['asset_b']

    st.divider()

    # Routing logic based on selected strategy
    if selected_strategy == "Pairs Trading (Classic Cointegration)":
        
        # --- PHASE 1: SETUP & DATA ALIGNMENT ---
        st.header("Phase 1: Setup & Data Alignment")
        
        # 1. UI Parameters
        with st.expander("⚙️ Step 1: Define Rules & Capital", expanded=True):
            st.markdown("Before calculating any math, we need to define the environment constraints.")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**Execution Costs**")
                capital = st.number_input("Total Capital Allocation ($)", min_value=100.0, value=10000.0, step=1000.0, key="phase1_capital")
                fee_rate = st.number_input("Exchange Fee Rate (%)", min_value=0.0, value=0.05, step=0.01, key="phase1_fee") / 100.0
                slippage = st.number_input("Slippage (%)", min_value=0.0, value=0.02, step=0.01, key="phase1_slippage") / 100.0
            with c2:
                st.markdown("**Statistical Windows**")
                coint_window_input = st.number_input(
                    "Cointegration Window (Bars)", 
                    min_value=10, 
                    value=int(coint_window_default),
                    help="How many bars to look back to calculate the OLS regression (Hedge Ratio).",
                    key="phase1_coint_window"
                )
                z_window = st.number_input("Z-Score MA Window (Bars)", min_value=10, value=30, help="Smoothing window for the spread oscillator.", key="phase1_z_window")
            with c3:
                st.markdown("**Regime Filters (P-Value)**")
                coint_entry = st.number_input("Entry Barrier (Start Trading)", min_value=0.01, max_value=1.0, value=0.10, step=0.01, key="phase1_coint_entry")
                coint_cutoff = st.number_input("Emergency Cutoff (Kill Switch)", min_value=0.05, max_value=1.0, value=0.40, step=0.01, key="phase1_coint_cutoff")
                
            st.markdown("**Z-Score Triggers**")
            c4, c5 = st.columns(2)
            with c4:
                z_entry = st.number_input("Z-Score Entry", min_value=1.0, value=2.0, step=0.1, key="phase1_z_entry")
            with c5:
                z_exit = st.number_input("Z-Score Exit", min_value=-1.0, value=0.0, step=0.1, key="phase1_z_exit")
        
        st.divider()

        # 2. Raw Data Fetching
        st.markdown("### 📊 Raw Asset Correlation")
        st.markdown(f"Fetching deep historical `{timeframe}` data for **{asset_a}** and **{asset_b}**...")
        
        with st.spinner("Loading market data..."):
            try:
                loader = DataLoader([asset_a, asset_b], timeframe)
                close_df, _, _ = loader.load()
                # Forward fill missing data to align timestamps, then drop rows where both don't exist
                df_pair = close_df[[asset_a, asset_b]].ffill().dropna()
                
            except Exception as e:
                st.error(f"Failed to load market data: {e}")
                return
                
        if df_pair.empty:
            st.error("Data missing for these assets.")
            return
            
        # Call the external component to render the raw data chart
        from src.strategies.pairs.components.render_raw_data import plot_raw_normalized_prices
        plot_raw_normalized_prices(df_pair, asset_a, asset_b)
        
        st.divider()

        # --- PHASE 2: SPREAD & STATISTICAL CORE ---
        st.header("Phase 2: Spread & Statistical Core")
        from src.strategies.pairs.components.render_spread import plot_spread_and_regime
        spread, smoothed_p_values, rolling_beta = plot_spread_and_regime(
            df_pair, asset_a, asset_b,
            coint_window=coint_window_input,
            coint_entry=coint_entry,
            coint_cutoff=coint_cutoff
        )
        
        if spread is None:
            return  # Stop pipeline if Phase 2 fails (e.g. not enough data)
            
        st.divider()

        # --- PHASE 3: SIGNAL GENERATION ---
        st.header("Phase 3: Signal Generation")
        from src.strategies.pairs.components.render_signals import render_zscore_and_signals
        
        signals_df, z_score = render_zscore_and_signals(
            spread, smoothed_p_values,
            z_window=z_window,
            z_entry=z_entry,
            z_exit=z_exit,
            coint_entry=coint_entry,
            coint_cutoff=coint_cutoff
        )
        
        if signals_df is None:
            return
            
        st.divider()

        # --- PHASE 4: EXECUTION ENGINE & WEIGHTS ---
        st.header("Phase 4: Execution Engine & Weights")
        from src.strategies.pairs.components.render_engine import render_engine_execution
        
        render_engine_execution(
            df_pair=df_pair,
            signals_df=signals_df,
            rolling_beta=rolling_beta,
            asset_a=asset_a,
            asset_b=asset_b,
            capital=capital,
            fee_rate=fee_rate,
            slippage=slippage
        )
        
        st.divider()
