import streamlit as st
import pandas as pd
from src.dashboard.styles import apply_compact_styles
from src.data.basket import BasketManager
from src.engine.data.loader import DataLoader
from src.strategies.factory import StrategyFactory

def render_strategy_page():
    apply_compact_styles()

    st.title("Strategy Lab (Deep Inspection)")
    st.markdown("Select a proven Alpha Basket, then pick **one pair** to step through the mathematical execution pipeline visually.")
    
    # 0. Strategy Documentation
    import os
    
    # 1. Strategy Selection
    strategy_options = list(StrategyFactory.STRATEGY_REGISTRY.keys())
    col_s, col_b, col_p = st.columns(3)
    
    with col_s:
        selected_strategy = st.selectbox("1. Select Strategy", strategy_options)

    # 2. Load config & instantiate strategy
    config = StrategyFactory.get_default_config(selected_strategy)
    strategy = StrategyFactory.create(config)

    # Show README if available
    module_path = StrategyFactory.STRATEGY_REGISTRY[selected_strategy].rsplit('.', 2)[0]
    readme_path = os.path.join(module_path.replace(".", os.sep), "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, "r") as f:
            readme_content = f.read()
        with st.expander("📖 Strategy Documentation & Rules", expanded=False):
            st.markdown(readme_content)

    # 3. Basket Selection (Filtered by strategy)
    all_baskets = BasketManager.list_baskets(basket_type="strategy")
    
    compatible_baskets = []
    for b in all_baskets:
        meta_strat = b.get("metadata", {}).get("strategy_name")
        if meta_strat == selected_strategy or meta_strat is None:
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
    
    # 4. Pair Selection
    pair_strs = [f"{p['asset_a']} / {p['asset_b']}" for p in pairs]
    
    with col_p:
        selected_pair_str = st.selectbox("3. Select Pair to Inspect", pair_strs)
        
    selected_pair_idx = pair_strs.index(selected_pair_str)
    p = pairs[selected_pair_idx]
    asset_a = p['asset_a']
    asset_b = p['asset_b']

    st.divider()

    # --- PHASE 1: SETUP & DATA ALIGNMENT ---
    st.header("Phase 1: Setup & Data Alignment")
    
    # Strategy renders its own parameter UI
    params = strategy.render_parameters(st)
    
    st.divider()

    # Data Loading (strategy-agnostic)
    st.markdown(f"### 📊 Raw Asset Correlation")
    st.markdown(f"Fetching deep historical `{timeframe}` data for **{asset_a}** and **{asset_b}**...")
    
    with st.spinner("Loading market data..."):
        try:
            loader = DataLoader([asset_a, asset_b], timeframe)
            close_df, _, _ = loader.load()
            df_pair = close_df[[asset_a, asset_b]].ffill().dropna()
        except Exception as e:
            st.error(f"Failed to load market data: {e}")
            return
            
    if df_pair.empty:
        st.error("Data missing for these assets.")
        return

    # Strategy renders its own pipeline (Phases 2, 3, 4, ...)
    strategy.render_pipeline(st, df_pair, asset_a, asset_b, params)
