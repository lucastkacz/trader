import streamlit as st
import pandas as pd
import plotly.express as px
from src.dashboard.styles import apply_compact_styles
from src.data.basket import BasketManager
from src.engine.data.loader import DataLoader
from src.strategies.pairs import PairsTradingStrategy

def render_strategy_page():
    apply_compact_styles()

    st.title("Strategy Lab")
    st.markdown("Execute backtests against mathematically proven Alpha Baskets.")

    # 1. Basket Selection
    st.write("### Basket Selection")
    baskets = BasketManager.list_baskets()
    
    if not baskets:
        st.warning("No Baskets found. Please run Alpha Discovery and save a basket first.")
        return
        
    basket_names = [b.get("name", "Unknown") for b in baskets]
    
    col_b1, col_b2 = st.columns([1, 2])
    with col_b1:
        selected_b_name = st.selectbox("Select Basket", basket_names)
    
    selected_basket = next((b for b in baskets if b.get("name") == selected_b_name), None)
    
    if selected_basket:
        pairs = selected_basket.get('pairs', [])
        timeframe = selected_basket.get('timeframe', '1h')
        universe = selected_basket.get('universe_name', 'Unknown')
        
        with col_b2:
            st.write("") # Spacing alignment
            st.write("")
            st.markdown(f"**Pairs:** {len(pairs)} &nbsp;&nbsp;|&nbsp;&nbsp; **Timeframe:** {timeframe} &nbsp;&nbsp;|&nbsp;&nbsp; **Universe:** {universe}")
        
        # Display the pairs in an expander instead of sidebar
        with st.expander("View Basket Pairs"):
            if pairs:
                pair_strs = [f"**{p['asset_a']}/{p['asset_b']}** (p={p.get('p_value', p.get('latest_p_value', 0.0)):.4f})" for p in pairs]
                st.markdown(" • ".join(pair_strs))

    st.divider()

    # 2. Strategy Parameters
    st.write("### Strategy Parameters")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Entry & Exit Logic**")
        strategy_type = st.selectbox("Execution Logic", ["Z-Score Basic"])
        z_window = st.number_input("Z-Score Window", min_value=10, value=30, help="Moving average window for entry signals")
        
    with col2:
        st.markdown("**Thresholds**")
        z_entry = st.number_input("Z-Score Entry", min_value=1.0, value=2.0, step=0.1, help="Deviation required to enter spread")
        z_exit = st.number_input("Z-Score Exit", min_value=-1.0, value=0.0, step=0.1, help="Deviation required to exit spread")
        
    with col3:
        st.markdown("**Portfolio & Engine Settings**")
        capital_per_pair = st.number_input("Capital per Pair ($)", min_value=1000.0, value=10000.0, step=1000.0)
        fee_rate = st.number_input("Exchange Fee Rate (%)", min_value=0.0, value=0.05, step=0.01) / 100.0
        slippage = st.number_input("Slippage (%)", min_value=0.0, value=0.02, step=0.01) / 100.0

    st.divider()

    # 3. Execution
    if st.button("⚡ Run Vectorized Backtest", type="primary", use_container_width=True):
        if not selected_basket or not selected_basket.get('pairs'):
            st.error("Invalid Basket.")
            return
            
        pairs = selected_basket['pairs']
        timeframe = selected_basket.get('timeframe', '1h')
        
        # Get unique symbols needed from basket
        symbols_needed = set()
        for p in pairs:
            symbols_needed.add(p['asset_a'])
            symbols_needed.add(p['asset_b'])
            
        with st.spinner(f"Running vectorized engine on {len(pairs)} pairs..."):
            try:
                # Load Data
                loader = DataLoader(list(symbols_needed), timeframe)
                close_df, _, _ = loader.load()
                
                if close_df.empty:
                    st.error("No data found for the symbols in this basket.")
                    return
                
                # Setup Strategy (Note: We reuse PairsTradingStrategy but we bypass the Alpha Discovery math)
                # We will force the `evaluate_pair` to pass Cointegration immediately since it's already proven.
                # Actually, our current PairsTradingStrategy recalculates Cointegration inside `evaluate_pair`.
                # Let's use the provided `PairsTradingStrategy` class for seamless integration, knowing it validates
                # the regime filter internally (which is robust).
                
                # To make Strategy Lab incredibly fast, we set coint_window to standard so it can generate the rolling spread.
                # Wait, the rolling spread needs a window. We should use 90 or allow user to configure it.
                # Assuming 90 for now or user input. Let's add it to UI implicitly or grab from params.
                coint_window_c = 90 # Defaulting for spread gen
                
                strategy = PairsTradingStrategy(
                    timeframe=timeframe,
                    cointegration_window=coint_window_c,
                    cointegration_p_value_threshold=0.99, # Bypass regime filter for pure execution speed test, or keep strict. 
                    zscore_window=z_window,
                    entry_threshold=z_entry,
                    exit_threshold=z_exit,
                    capital_per_pair=capital_per_pair,
                    fee_rate=fee_rate,
                    slippage=slippage
                )
                
                results_list = []
                progress_bar = st.progress(0)
                
                for idx, p in enumerate(pairs):
                    asset_a = p['asset_a']
                    asset_b = p['asset_b']
                    
                    # This runs Math + Signals + Weights + VectorizedEngine
                    metrics = strategy.evaluate_pair(asset_a, asset_b, close_df)
                    
                    if metrics and metrics.get('status') == 'Success':
                        metrics['correlation_alpha_phase'] = p.get('correlation', 0)
                        results_list.append(metrics)
                        
                    progress_bar.progress((idx + 1) / len(pairs))
                    
                progress_bar.empty()
                
                # 4. Results
                if not results_list:
                    st.warning("Strategy failed to generate valid backtests.")
                else:
                    results_df = pd.DataFrame(results_list)
                    results_df = results_df.sort_values('sharpe_ratio', ascending=False)
                    
                    st.success(f"Backtest Complete! Rendered Strategy Logic across {len(results_df)} Pairs in Basket.")
                    
                    # Portfolio sum approximations
                    st.write("### Portfolio Summary")
                    total_pnl = results_df['total_return_pct'].sum() * capital_per_pair / 100.0  # simple sum
                    avg_sharpe = results_df['sharpe_ratio'].mean()
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Gross Basket PnL", f"${total_pnl:,.2f}")
                    m2.metric("Average Pair Sharpe", f"{avg_sharpe:.2f}")
                    m3.metric("Capital Deployed", f"${capital_per_pair * len(results_df):,.2f}")
                    
                    st.write("### Detailed Pair Results")
                    st.dataframe(
                        results_df[['asset_a', 'asset_b', 'total_return_pct', 'sharpe_ratio', 'max_drawdown_pct', 'final_equity']].style.format({
                            'total_return_pct': "{:.2f}%",
                            'sharpe_ratio': "{:.2f}",
                            'max_drawdown_pct': "{:.2f}%",
                            'final_equity': "${:,.2f}"
                        }),
                        use_container_width=True
                    )
                    
                    st.divider()
                    st.write("### Equity Curves")
                    
                    # Rather than recalculating like the Screener, we just plot the fastest logic again.
                    # Or we refactor slightly to just recalculate the Top 3 to prevent freezing.
                    top_3 = results_df.head(3)
                    for idx, row in top_3.iterrows():
                        a = row['asset_a']
                        b = row['asset_b']
                        with st.expander(f"📈 {a} & {b} (Sharpe: {row['sharpe_ratio']:.2f})", expanded=True):
                            with st.spinner("Generating Equity Curve..."):
                                df_pair = close_df[[a, b]].ffill().dropna()
                                from src.engine.core.engine import VectorizedEngine
                                engine = VectorizedEngine(initial_capital=capital_per_pair, fee_rate=fee_rate, slippage=slippage)
                                
                                from src.stats.cointegration import calculate_rolling_spread
                                from src.stats.zscore import calculate_z_score, generate_signals
                                
                                rolling_s, rolling_b = calculate_rolling_spread(df_pair[a], df_pair[b], window=coint_window_c)
                                z = calculate_z_score(rolling_s, window=z_window)
                                sigs = generate_signals(z, entry_threshold=z_entry, exit_threshold=z_exit)
                                
                                pos = sigs['position']
                                
                                w = pd.DataFrame(0.0, index=df_pair.index, columns=df_pair.columns)
                                w[a] = pos
                                w[b] = pos * (-rolling_b)
                                w = w.fillna(0.0)
                                
                                res = engine.run(df_pair, w)
                                
                                fig = px.line(res, x=res.index, y='equity', title=f"Equity Curve: {a}/{b} (After Slippage & Fees)")
                                st.plotly_chart(fig, use_container_width=True)
                                
            except Exception as e:
                st.error(f"Strategy execution failed: {str(e)}")
