import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from src.engine.core.engine import VectorizedEngine
from src.strategies.pairs.strategy import StrategyLogger
from src.strategies.pairs.weighting import calculate_beta_neutral_weights

def render_engine_execution(df_pair: pd.DataFrame, signals_df: pd.DataFrame, rolling_beta: pd.Series, asset_a: str, asset_b: str, capital: float, fee_rate: float, slippage: float, stop_loss_pct: float = 0.0):
    """
    Renders Phase 4: Execution Engine & Weights.
    """
    if signals_df is None or signals_df.empty:
        return
        
    st.markdown("### ⚙️ Engine Execution: From Signals to Dollars")
    st.markdown(
        "To backtest this, we translate the `+1 / 0 / -1` abstract signals into **Target Portfolio Weights**. "
        "We use **Normalized Beta-Neutral Weighting** to dynamically allocate capital based on the rolling Hedge Ratio. "
        "Safety guardrails (clipping) ensure no single asset ever consumes more than 85% or less than 15% of the portfolio."
    )
    
    with st.spinner("Executing Vectorized Backtest Engine..."):
        # 1. GENERATE TARGET WEIGHTS
        weights = calculate_beta_neutral_weights(df_pair, signals_df, rolling_beta, asset_a, asset_b)
        
        # 2. RUN VECTORIZED ENGINE
        engine = VectorizedEngine(initial_capital=capital, fee_rate=fee_rate, slippage=slippage)
        sl = stop_loss_pct / 100.0 if stop_loss_pct > 0 else None
        results = engine.run(df_pair, weights, stop_loss_pct=sl)
        trade_log = engine.get_trade_history()
        stop_events = results.attrs.get('stop_events', [])
        stop_timestamps = {ev[0] for ev in stop_events}  # set of bar timestamps where stops fired

    # -----------------------------------------------------------------------
    # BUILD ROUND-TRIP LIST (needed for both chart and table)
    # -----------------------------------------------------------------------
    equity = results['equity']
    raw = trade_log.copy().sort_values(by=["Date", "Asset"]).reset_index(drop=True) if not trade_log.empty else pd.DataFrame()
    timestamps = raw['Date'].unique() if not raw.empty else []

    round_trips = []      # list of dicts
    trip_spans  = []      # list of (t_open, t_close, direction) for chart shading

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
        eq_before_open = open_orders['Current Equity ($)'].iloc[0]
        eq_after_close = close_orders['Current Equity ($)'].iloc[-1]
        rt_pnl         = eq_after_close - eq_before_open
        
        a_order   = open_orders[open_orders['Asset'] == asset_a]
        direction = "LONG SPREAD" if (not a_order.empty and a_order['Delta Weight'].iloc[0] > 0) else "SHORT SPREAD"
        
        duration_hrs = (t_close - t_open).total_seconds() / 3600
        duration_str = (
            f"{int(duration_hrs // 24)}d {int(duration_hrs % 24)}h"
            if duration_hrs >= 24
            else f"{duration_hrs:.0f}h"
        )

        # Check if this trade was stopped
        was_stopped = any(
            stop_ts >= t_open and stop_ts <= t_close
            for stop_ts in stop_timestamps
        )
        status = "⛔ STOPPED" if was_stopped else "✅ CLOSED"
        
        round_trips.append({
            "Trade #":        len(round_trips) + 1,
            "Direction":      direction,
            "Status":         status,
            "Opened":         t_open.strftime("%Y-%m-%d %H:%M"),
            "Closed":         t_close.strftime("%Y-%m-%d %H:%M"),
            "Duration":       duration_str,
            "Entry Notional": f"${entry_notional:,.2f}",
            "Exit Notional":  f"${exit_notional:,.2f}",
            "Total Fees":     f"${total_fees_rt:,.2f}",
            "P&L":            f"${rt_pnl:+,.2f}",
            "Equity After":   f"${eq_after_close:,.2f}",
        })
        trip_spans.append((t_open, t_close, direction))
        i += 2

    # -----------------------------------------------------------------------
    # PLOT EQUITY CURVE  
    # -----------------------------------------------------------------------
    roll_max   = equity.cummax()
    drawdown   = (equity - roll_max) / roll_max
    max_dd_idx = drawdown.idxmin()
    max_dd_val = drawdown.min() * 100

    fig = go.Figure()

    # --- Subtle shaded bands for each round-trip trade ---
    eq_min = equity.min()
    eq_max = equity.max()
    padding = (eq_max - eq_min) * 0.5 if eq_max != eq_min else capital * 0.02
    y_lo = eq_min - padding
    y_hi = eq_max + padding

    # Trade band traces — added FIRST so they sit below the equity line in z-order.
    # Using scatter fill='toself' (rectangle via 4 corner points) instead of
    # Plotly shapes, because shapes with layer='below' get painted over by the
    # equity fill='tozeroy' area.
    for t_open, t_close, direction in trip_spans:
        band_color = "rgba(33, 150, 243, 0.18)" if direction == "LONG SPREAD" else "rgba(255, 152, 0, 0.18)"
        edge_color  = "rgba(33, 150, 243, 0.4)"  if direction == "LONG SPREAD" else "rgba(255, 152, 0, 0.4)"
        fig.add_trace(go.Scatter(
            x=[t_open, t_close, t_close, t_open, t_open],
            y=[y_lo,   y_lo,    y_hi,    y_hi,   y_lo],
            fill='toself',
            fillcolor=band_color,
            line=dict(color=edge_color, width=0.8),
            mode='lines',
            showlegend=False,
            hoverinfo='skip',
        ))

    # Main equity line — added AFTER bands so it renders on top
    fig.add_trace(
        go.Scatter(
            x=equity.index,
            y=equity,
            name="Portfolio Equity",
            line=dict(color='#00E676', width=2),
        )
    )

    # Invisible dummy traces for the legend (trade direction colours)
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode='markers',
        name="Long Spread trade",
        marker=dict(size=10, color="rgba(33, 150, 243, 0.5)", symbol="square"),
        showlegend=True,
    ))
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode='markers',
        name="Short Spread trade",
        marker=dict(size=10, color="rgba(255, 152, 0, 0.5)", symbol="square"),
        showlegend=True,
    ))

    # Entry / exit tick marks on the equity line
    for t_open, t_close, direction in trip_spans:
        marker_color = "#2196F3" if direction == "LONG SPREAD" else "#FF9800"
        fig.add_trace(go.Scatter(
            x=[t_open, t_close],
            y=[equity.get(t_open, equity.iloc[0]), equity.get(t_close, equity.iloc[-1])],
            mode='markers',
            marker=dict(symbol='line-ns', size=10, color=marker_color,
                        line=dict(width=1.5, color=marker_color)),
            showlegend=False,
            hovertemplate=f"{'Open' if t_open else 'Close'} — {direction}<extra></extra>",
        ))

    # Initial capital reference
    fig.add_hline(y=capital, line_dash="dash", line_color="#E0E0E0", annotation_text="Initial Capital")

    # Max drawdown marker
    fig.add_trace(
        go.Scatter(
            x=[max_dd_idx],
            y=[equity.loc[max_dd_idx]],
            mode='markers',
            name=f"Max DD ({max_dd_val:.2f}%)",
            marker=dict(symbol='x', size=12, color='#FF1744', line=dict(width=2)),
        )
    )

    # Stop-loss markers (if any)
    if stop_events:
        stop_times = [ev[0] for ev in stop_events]
        stop_equities = [equity.get(t, equity.iloc[-1]) for t in stop_times]
        fig.add_trace(
            go.Scatter(
                x=stop_times,
                y=stop_equities,
                mode='markers',
                name=f"⛔ Stop Loss ({len(stop_events)})",
                marker=dict(symbol='octagon', size=14, color='#FF1744',
                            line=dict(width=2, color='white')),
            )
        )

    fig.update_layout(
        title="Historical Backtest Equity Curve",
        height=420,
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=60, r=40, t=60, b=40),
        yaxis=dict(tickprefix="$", tickformat=",.0f", range=[y_lo, y_hi]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------------------------
    # PLOT TARGET WEIGHTS
    # -----------------------------------------------------------------------
    from src.strategies.pairs.components.render_weights import plot_target_weights
    plot_target_weights(weights, rolling_beta, asset_a, asset_b)

    # -----------------------------------------------------------------------
    # METRICS
    # -----------------------------------------------------------------------
    total_pnl  = equity.iloc[-1] - capital
    return_pct = (total_pnl / capital) * 100
    total_fees = raw['Fees Paid ($)'].sum() if not raw.empty else 0.0
    fees_pct   = (total_fees / capital) * 100

    # Time metrics
    if trip_spans:
        first_open  = trip_spans[0][0]
        last_close  = trip_spans[-1][1]
        span_hrs    = (last_close - first_open).total_seconds() / 3600
        span_str    = f"{int(span_hrs // 24)}d {int(span_hrs % 24)}h" if span_hrs >= 24 else f"{span_hrs:.0f}h"

        in_trade_hrs = sum(
            (t_close - t_open).total_seconds() / 3600
            for t_open, t_close, _ in trip_spans
        )
        in_trade_str = f"{int(in_trade_hrs // 24)}d {int(in_trade_hrs % 24)}h" if in_trade_hrs >= 24 else f"{in_trade_hrs:.0f}h"
        in_trade_pct_str = f"{(in_trade_hrs / span_hrs * 100):.1f}% of span" if span_hrs > 0 else ""
    else:
        span_str = in_trade_str = in_trade_pct_str = "—"

    row1 = st.columns(4)
    row1[0].metric("Final Equity",    f"${equity.iloc[-1]:,.2f}", f"{return_pct:.2f}%")
    row1[1].metric("Net Profit",      f"${total_pnl:,.2f}")
    row1[2].metric("Max Drawdown",    f"{max_dd_val:.2f}%",  f"{max_dd_idx.strftime('%Y-%m-%d %H:%M')}", delta_color="off")
    row1[3].metric("Total Fees Paid", f"${total_fees:,.2f}", f"−{fees_pct:.2f}% of capital",            delta_color="inverse")

    row2 = st.columns(4)
    row2[0].metric("Round-Trip Trades", len(round_trips))
    row2[1].metric("Backtest Span",     span_str,       "First open → Last close", delta_color="off")
    row2[2].metric("Time in Trades",    in_trade_str,   in_trade_pct_str,           delta_color="off")
    row2[3].metric("Avg Trade Duration",
                   (f"{sum((t_close-t_open).total_seconds()/3600 for t_open,t_close,_ in trip_spans)/len(trip_spans):.0f}h"
                    if trip_spans else "—"))

    if stop_events:
        st.info(f"⛔ **{len(stop_events)} trade(s) stopped** by the {stop_loss_pct:.1f}% per-trade equity stop-loss.")

    # -----------------------------------------------------------------------
    # ROUND-TRIP TRADE LOG TABLE
    # -----------------------------------------------------------------------
    st.markdown("#### 📝 Round-Trip Trade Log")
    st.caption("Each row = one complete trade: Entry (2 orders) + Exit (2 orders). Shaded bands on the chart match each trade.")

    if not round_trips:
        st.info("No trades were executed during this period with the current parameters.")
    else:
        st.dataframe(pd.DataFrame(round_trips), use_container_width=True, hide_index=True)

        with st.expander("🔍 Raw Order-Level Detail"):
            display_df = raw.copy()
            display_df['Price']            = display_df['Price'].apply(lambda x: f"${x:,.4f}")
            display_df['Delta Weight']     = display_df['Delta Weight'].apply(lambda x: f"{x:,.4f}")
            display_df['Notional']         = display_df['Notional ($)'].apply(lambda x: f"${x:,.2f}")
            display_df['Fees Paid']        = display_df['Fees Paid ($)'].apply(lambda x: f"${x:,.2f}")
            display_df['Portfolio Equity'] = display_df['Current Equity ($)'].apply(lambda x: f"${x:,.2f}")
            display_df = display_df[['Date', 'Asset', 'Action', 'Price', 'Delta Weight', 'Notional', 'Fees Paid', 'Portfolio Equity']]
            st.dataframe(display_df, use_container_width=True, hide_index=True)
