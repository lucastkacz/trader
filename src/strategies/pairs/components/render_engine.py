import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from src.engine.core.engine import VectorizedEngine
from src.strategies.pairs.strategy import StrategyLogger

def render_engine_execution(df_pair: pd.DataFrame, signals_df: pd.DataFrame, rolling_beta: pd.Series, asset_a: str, asset_b: str, capital: float, fee_rate: float, slippage: float):
    """
    Renders Phase 4: Execution Engine & Weights.
    Takes the +/- 1 signals from Phase 3, translates them into Target Portfolio Weights
    (accounting for the dynamic Hedge Ratio), and feeds them into the VectorizedEngine.
    """
    if signals_df is None or signals_df.empty:
        return
        
    st.markdown("### ⚙️ Engine Execution: From Signals to Dollars")
    st.markdown(
        "To backtest this, we translate the `+1 / 0 / -1` abstract signals into **Target Portfolio Weights**. "
        "Each leg receives exactly **50% of capital**, making the portfolio dollar-neutral. "
        "The Hedge Ratio is already embedded in the spread construction and does not re-enter sizing."
    )
    
    with st.spinner("Executing Vectorized Backtest Engine..."):
        # 1. GENERATE TARGET WEIGHTS
        positions = signals_df['position']
        weights = pd.DataFrame(0.0, index=df_pair.index, columns=df_pair.columns)
        
        # Dollar-neutral sizing: each leg gets exactly 50% of capital.
        # Signal convention: +1 = long spread (long A, short B)
        #                    -1 = short spread (short A, long B)
        # The hedge ratio (beta) is already embedded in the spread/z-score
        # construction — it must NOT re-enter the capital allocation here.
        weights[asset_a] = positions * 0.5
        weights[asset_b] = positions * -0.5
        weights = weights.fillna(0.0)
        
        # 2. RUN VECTORIZED ENGINE
        engine = VectorizedEngine(initial_capital=capital, fee_rate=fee_rate, slippage=slippage)
        results = engine.run(df_pair, weights)
        trade_log = engine.get_trade_history()
        
    # --- PLOT EQUITY CURVE ---
    equity = results['equity']
    
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=equity.index, 
            y=equity, 
            name="Portfolio Equity",
            fill='tozeroy',
            line=dict(color='#00E676', width=2),
            fillcolor='rgba(0, 230, 118, 0.1)'
        )
    )
    
    # Add initial capital reference line
    fig.add_hline(y=capital, line_dash="dash", line_color="#E0E0E0", annotation_text="Initial Capital")
    
    # Mark the max drawdown point
    roll_max = equity.cummax()
    drawdown = (equity - roll_max) / roll_max
    max_dd_idx = drawdown.idxmin()
    max_dd_val = drawdown.min() * 100
    fig.add_trace(
        go.Scatter(
            x=[max_dd_idx],
            y=[equity.loc[max_dd_idx]],
            mode='markers',
            name=f"Max Drawdown ({max_dd_val:.2f}%)",
            marker=dict(symbol='x', size=12, color='#FF1744', line=dict(width=2)),
        )
    )
    
    # Auto-zoom Y-axis to actual equity range with padding
    eq_min = equity.min()
    eq_max = equity.max()
    padding = (eq_max - eq_min) * 0.5 if eq_max != eq_min else capital * 0.02
    y_lo = eq_min - padding
    y_hi = eq_max + padding

    fig.update_layout(
        title="Historical Backtest Equity Curve",
        height=400,
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=60, r=40, t=60, b=40),
        yaxis=dict(
            tickprefix="$",
            tickformat=",.0f",
            range=[y_lo, y_hi],
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # --- DISPLAY METRICS ---
    total_pnl = equity.iloc[-1] - capital
    return_pct = (total_pnl / capital) * 100
    total_fees = trade_log['Fees Paid ($)'].sum() if not trade_log.empty else 0.0
    fees_pct = (total_fees / capital) * 100
    num_round_trips = len(trade_log) // 4 if not trade_log.empty else 0  # 4 orders per round-trip
    
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Final Equity", f"${equity.iloc[-1]:,.2f}", f"{return_pct:.2f}%")
    c2.metric("Net Profit", f"${total_pnl:,.2f}")
    c3.metric("Max Drawdown", f"{max_dd_val:.2f}%", f"{max_dd_idx.strftime('%Y-%m-%d %H:%M')}", delta_color="off")
    c4.metric("Total Fees Paid", f"${total_fees:,.2f}", f"−{fees_pct:.2f}% of capital", delta_color="inverse")
    c5.metric("Round-Trip Trades", num_round_trips)
    
    # --- GROUPED TRADE LOG ---
    st.markdown("#### 📝 Round-Trip Trade Log")
    st.caption("Each row = one complete trade: Entry (2 orders) + Exit (2 orders). Individual orders are shown inside.")
    
    if trade_log.empty:
        st.info("No trades were executed during this period with the current parameters.")
    else:
        # Group raw orders into round-trips.
        # A round-trip = 4 consecutive orders sharing the same position lifecycle.
        # Strategy: re-index by 'Date' changes — each position switch generates 2 orders (one per asset).
        # We pair consecutive position-open events with the next position-close events.
        
        raw = trade_log.copy()
        raw = raw.sort_values(by=["Date", "Asset"]).reset_index(drop=True)
        
        # Each unique timestamp has exactly 2 orders (one per asset).
        timestamps = raw['Date'].unique()
        
        round_trips = []
        i = 0
        while i < len(timestamps) - 1:
            t_open  = timestamps[i]
            t_close = timestamps[i + 1]
            
            open_orders  = raw[raw['Date'] == t_open]
            close_orders = raw[raw['Date'] == t_close]
            
            if open_orders.empty or close_orders.empty:
                i += 1
                continue
            
            entry_notional = open_orders['Notional ($)'].sum()
            exit_notional  = close_orders['Notional ($)'].sum()
            total_fees_rt  = open_orders['Fees Paid ($)'].sum() + close_orders['Fees Paid ($)'].sum()
            
            # PnL approximation: equity at close vs equity before open
            eq_before_open  = open_orders['Current Equity ($)'].iloc[0]
            eq_after_close  = close_orders['Current Equity ($)'].iloc[-1]
            rt_pnl          = eq_after_close - eq_before_open
            
            # Determine direction from the asset_a order (positive weight = long A = long spread)
            a_order = open_orders[open_orders['Asset'] == asset_a]
            direction = "LONG SPREAD" if (not a_order.empty and a_order['Delta Weight'].iloc[0] > 0) else "SHORT SPREAD"
            
            # Build compact order detail string
            def fmt_orders(orders):
                lines = []
                for _, r in orders.iterrows():
                    lines.append(f"{r['Asset']} {r['Action']} @ ${r['Price']:,.2f} | ${r['Notional ($)']:,.2f}")
                return "\n".join(lines)
            
            round_trips.append({
                "Trade #": len(round_trips) + 1,
                "Direction": direction,
                "Opened": t_open.strftime("%Y-%m-%d %H:%M"),
                "Closed": t_close.strftime("%Y-%m-%d %H:%M"),
                "Entry Notional": f"${entry_notional:,.2f}",
                "Exit Notional":  f"${exit_notional:,.2f}",
                "Total Fees":     f"${total_fees_rt:,.2f}",
                "P&L":            f"${rt_pnl:+,.2f}",
                "Equity After":   f"${eq_after_close:,.2f}",
            })
            i += 2  # skip to next pair of timestamps
        
        if round_trips:
            rt_df = pd.DataFrame(round_trips)
            st.dataframe(rt_df, use_container_width=True, hide_index=True)
        
        # Raw orders in an expander for those who want full detail
        with st.expander("🔍 Raw Order-Level Detail"):
            display_df = raw.copy()
            display_df['Price']           = display_df['Price'].apply(lambda x: f"${x:,.4f}")
            display_df['Delta Weight']    = display_df['Delta Weight'].apply(lambda x: f"{x:,.4f}")
            display_df['Notional']        = display_df['Notional ($)'].apply(lambda x: f"${x:,.2f}")
            display_df['Fees Paid']       = display_df['Fees Paid ($)'].apply(lambda x: f"${x:,.2f}")
            display_df['Portfolio Equity']= display_df['Current Equity ($)'].apply(lambda x: f"${x:,.2f}")
            display_df = display_df[['Date', 'Asset', 'Action', 'Price', 'Delta Weight', 'Notional', 'Fees Paid', 'Portfolio Equity']]
            st.dataframe(display_df, use_container_width=True, hide_index=True)
