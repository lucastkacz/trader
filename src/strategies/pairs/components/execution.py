import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime
from src.engine.core.engine import VectorizedEngine

def render_execution(df_pair: pd.DataFrame, signals: pd.DataFrame, rolling_beta: pd.Series, 
                     asset_a: str, asset_b: str, capital: float, fee_rate: float, slippage: float,
                     trade_log: pd.DataFrame = None, report_text: str = None, results_df: pd.DataFrame = None, basket_name: str = "Unknown",
                     raw_a: pd.DataFrame = None, raw_b: pd.DataFrame = None):
    """
    Renders Module 4: Engine Execution.
    Translates the filtered Long/Short signals into Target Portfolio Weights,
    runs the Vectorized Engine, and visualizes the Final Equity Curve.
    """
    st.write("### 💵 Module 4: Engine Execution")
    st.markdown(
        "Translating Signals into **Target Portfolio Weights** and simulating real-world execution "
        "complete with exchange fees and slippage."
    )
    
    if signals.empty or df_pair.empty:
        st.warning("No signals available to execute.")
        return

    if results_df is None or results_df.empty:
        st.warning("Engine failed to execute or return valid results.")
        return
            
    # Calculate KPIs
    pos = signals['filtered_position']
    final_equity = results_df['equity'].iloc[-1]
    total_return = (final_equity / capital - 1) * 100
    peak = results_df['equity'].cummax()
    drawdown = (results_df['equity'] - peak) / peak * 100
    max_dd = drawdown.min()
    
    # Simple Sharpe (Annualized approx for hours)
    returns = results_df['equity'].pct_change().dropna()
    mean_ret = returns.mean()
    std_ret = returns.std()
    sharpe = (mean_ret / std_ret) * (8760 ** 0.5) if std_ret > 0 else 0.0 # 8760 hours in a year
    
    # 4. KPI Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Final Equity", f"${final_equity:,.2f}", f"{total_return:,.2f}%")
    col2.metric("Sharpe Ratio", f"{sharpe:.2f}")
    col3.metric("Max Drawdown", f"{max_dd:.2f}%")
    
    # Count exact number of trades taken (where position flipped)
    trades_taken = (pos != pos.shift(1)).sum() - 1 # Subtract 1 for initial 0
    if trades_taken < 0: trades_taken = 0
    col4.metric("Trades Executed", f"{trades_taken}")

    # 5. Equity Curve Plot
    fig = px.line(
        results_df, 
        x=results_df.index, 
        y='equity', 
        title="Strategy Equity Curve (Net of Fees & Slippage)"
    )
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Equity ($)",
        template="plotly_dark",
        hovermode="x unified",
        margin=dict(l=40, r=40, t=40, b=40)
    )
    
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 5.5 Candlestick Execution Charts
    if raw_a is not None and raw_b is not None and trade_log is not None and not trade_log.empty:
        st.write("#### 🕯️ Trade Execution Explorer")
        st.markdown("Visual validation of exactly where the bot executed Buy/Sell orders overlaid on candlestick price action.")
        
        # Helper to plot candlesticks
        def plot_candlestick_with_trades(raw_df, asset_name, trades_df):
            fig_candle = go.Figure()
            
            # 1. Add Candlestick trace
            fig_candle.add_trace(go.Candlestick(
                x=raw_df.index,
                open=raw_df['open'],
                high=raw_df['high'],
                low=raw_df['low'],
                close=raw_df['close'],
                name=asset_name
            ))
            
            # 2. Add Trade Markers
            asset_trades = trades_df[trades_df['Asset'] == asset_name]
            buys = asset_trades[asset_trades['Action'] == 'BUY']
            sells = asset_trades[asset_trades['Action'] == 'SELL']
            
            if not buys.empty:
                fig_candle.add_trace(go.Scatter(
                    x=buys['Date'], y=buys['Price'] * 0.999,
                    mode='markers',
                    marker=dict(symbol='triangle-up', color='#00E676', size=14, line=dict(color='white', width=1)),
                    name='Buy Executed'
                ))
            if not sells.empty:
                fig_candle.add_trace(go.Scatter(
                    x=sells['Date'], y=sells['Price'] * 1.001,
                    mode='markers',
                    marker=dict(symbol='triangle-down', color='#FF1744', size=14, line=dict(color='white', width=1)),
                    name='Sell Executed'
                ))
                
            fig_candle.update_layout(
                title=f"{asset_name} Price Action & Executions",
                template="plotly_dark",
                xaxis_rangeslider_visible=False,
                margin=dict(l=40, r=40, t=40, b=40),
                height=400
            )
            return fig_candle
            
        # Draw side by side
        ca, cb = st.columns(2)
        with ca:
            st.plotly_chart(plot_candlestick_with_trades(raw_a, asset_a, trade_log), use_container_width=True)
        with cb:
            st.plotly_chart(plot_candlestick_with_trades(raw_b, asset_b, trade_log), use_container_width=True)
    
    # 6. Deep Strategy Report (Comprehensive Text Log)
    if report_text:
        st.write("#### 🔎 Deep Trade Inspector & Strategy Report")
        st.markdown(
            "A complete text report generated by the engine containing general info, "
            "baskets, parameters used, the total trades executed, and the exact chronological trade log."
        )
        
        with st.expander("Generate & Inspect Full Report", expanded=False):
            st.code(report_text, language="text")
            
        st.write("---")
        # Ensure data folder exists
        log_dir = os.path.join("data", "strategy_logs")
        os.makedirs(log_dir, exist_ok=True)
        
        c1, c2 = st.columns([1, 3])
        with c1:
            if st.button("💾 Save Report to /data/strategy_logs", use_container_width=True):
                # Sanitize basket name
                safe_basket = "".join([c if c.isalnum() else "_" for c in basket_name])
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"strategy_pairs_{safe_basket}_{timestamp}.txt"
                filepath = os.path.join(log_dir, filename)
                
                try:
                    with open(filepath, "w") as f:
                        f.write(report_text)
                    st.success(f"Log saved successfully! \n\n📁 `{filepath}`")
                except Exception as e:
                    st.error(f"Failed to save log: {e}")
