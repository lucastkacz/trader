"""
Per-trade price inspector.

Renders a dropdown to select a specific round-trip trade and displays a
chart where both assets are re-normalized to base 100 at the trade entry
timestamp. This makes it trivial to see exactly how the two legs diverged
(or converged) during the holding period.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go


def _build_round_trips(signals_df: pd.DataFrame):
    """
    Extract (entry_time, exit_time, direction) tuples from the signals
    DataFrame positions column.
    """
    positions = signals_df["position"]
    pos_diff = positions.diff().fillna(0)

    trips = []
    current_dir = None
    current_open = None

    for ts in pos_diff[pos_diff != 0].index:
        pos = positions.loc[ts]
        if pos != 0 and current_dir is None:
            current_dir = "LONG SPREAD" if pos == 1 else "SHORT SPREAD"
            current_open = ts
        elif pos == 0 and current_dir is not None:
            trips.append((current_open, ts, current_dir))
            current_dir = None
            current_open = None

    return trips


def render_trade_inspector(
    df_pair: pd.DataFrame,
    signals_df: pd.DataFrame,
    asset_a: str,
    asset_b: str,
    stop_events: list = None,
):
    """
    Dropdown trade selector + per-trade normalized price chart.
    """
    trips = _build_round_trips(signals_df)

    if not trips:
        st.info("No completed round-trip trades to inspect.")
        return

    # ── Dropdown ─────────────────────────────────────────────────────
    labels = [
        f"Trade #{i+1} — {d} — {o.strftime('%b %d %H:%M')} → {c.strftime('%b %d %H:%M')}"
        for i, (o, c, d) in enumerate(trips)
    ]

    selected = st.selectbox("Select a round-trip trade to inspect", labels, key="trade_inspector_select")
    idx = labels.index(selected)
    t_open, t_close, direction = trips[idx]

    # ── Determine which asset is long, which is short ────────────────
    if direction == "LONG SPREAD":
        long_asset, short_asset = asset_a, asset_b
    else:
        long_asset, short_asset = asset_b, asset_a

    # ── Slice & normalize prices to base 100 at trade entry ──────────
    # Add a small context window: 12 bars before and 6 bars after
    freq = df_pair.index[1] - df_pair.index[0] if len(df_pair) > 1 else pd.Timedelta(hours=1)
    ctx_before = t_open - freq * 12
    ctx_after  = t_close + freq * 6
    mask = (df_pair.index >= ctx_before) & (df_pair.index <= ctx_after)
    window = df_pair.loc[mask]

    if window.empty or t_open not in df_pair.index:
        st.warning("Not enough data around this trade to render the chart.")
        return

    base_a = df_pair.loc[t_open, asset_a]
    base_b = df_pair.loc[t_open, asset_b]
    norm_a = (window[asset_a] / base_a) * 100
    norm_b = (window[asset_b] / base_b) * 100

    # ── Chart ────────────────────────────────────────────────────────
    fig = go.Figure()

    # Trade-active shading
    y_lo = min(norm_a.min(), norm_b.min()) - 0.3
    y_hi = max(norm_a.max(), norm_b.max()) + 0.3
    band_color = "rgba(33,150,243,0.10)" if direction == "LONG SPREAD" else "rgba(255,152,0,0.10)"

    fig.add_trace(go.Scatter(
        x=[t_open, t_close, t_close, t_open, t_open],
        y=[y_lo,   y_lo,    y_hi,    y_hi,   y_lo],
        fill="toself", fillcolor=band_color,
        line=dict(width=0), mode="lines",
        showlegend=False, hoverinfo="skip",
    ))

    # Normalized price lines
    long_color  = "#00E676"   # green
    short_color = "#FF1744"   # red

    fig.add_trace(go.Scatter(
        x=norm_a.index, y=norm_a,
        name=f"{'📈 LONG' if asset_a == long_asset else '📉 SHORT'} {asset_a}",
        line=dict(color=long_color if asset_a == long_asset else short_color, width=2.5),
    ))
    fig.add_trace(go.Scatter(
        x=norm_b.index, y=norm_b,
        name=f"{'📈 LONG' if asset_b == long_asset else '📉 SHORT'} {asset_b}",
        line=dict(color=long_color if asset_b == long_asset else short_color, width=2.5),
    ))

    # Entry / Exit vertical lines (manual shapes to avoid pandas Timestamp + int bug in add_vline)
    is_stopped = stop_events is not None and any(ev[0] == t_close and ev[1] == t_open for ev in stop_events)

    for ts, label, color in [(t_open, "OPEN", "white"), (t_close, "⛔ STOP LOSS" if is_stopped else "CLOSE", "#FF1744" if is_stopped else "#BDBDBD")]:
        fig.add_shape(
            type="line", xref="x", yref="paper",
            x0=ts, x1=ts, y0=0, y1=1,
            line=dict(color=color, width=1.5 if is_stopped else 1, dash="dash"),
        )
        fig.add_annotation(
            x=ts, y=1, yref="paper", text=label,
            showarrow=False, font=dict(color=color, size=10, weight="bold" if is_stopped else "normal"),
            yshift=8,
        )

    # Base-100 reference
    fig.add_hline(y=100, line_dash="dot", line_color="#757575", line_width=0.8)

    # Duration label
    dur_hrs = (t_close - t_open).total_seconds() / 3600
    dur_str = f"{int(dur_hrs // 24)}d {int(dur_hrs % 24)}h" if dur_hrs >= 24 else f"{dur_hrs:.0f}h"

    fig.update_layout(
        title=f"Trade #{idx+1}: {direction}  •  {dur_str}  •  Prices rebased to 100 at entry",
        height=420,
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=40, r=40, t=60, b=40),
        yaxis=dict(title="Rebased Price (100 = entry)", range=[y_lo, y_hi]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig, use_container_width=True)

    # ── Quick stats ──────────────────────────────────────────────────
    entry_a = df_pair.loc[t_open, asset_a]
    entry_b = df_pair.loc[t_open, asset_b]
    exit_a  = df_pair.loc[t_close, asset_a]
    exit_b  = df_pair.loc[t_close, asset_b]

    ret_a = (exit_a / entry_a - 1) * 100
    ret_b = (exit_b / entry_b - 1) * 100

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"{long_asset} (LONG)", f"{ret_a if long_asset == asset_a else ret_b:+.2f}%")
    c2.metric(f"{short_asset} (SHORT)", f"{ret_a if short_asset == asset_a else ret_b:+.2f}%")

    # Spread return: long leg return - short leg return
    long_ret  = ret_a if long_asset == asset_a else ret_b
    short_ret = ret_a if short_asset == asset_a else ret_b
    spread_ret = long_ret - short_ret
    c3.metric("Spread Return", f"{spread_ret:+.2f}%")
    c4.metric("Duration", dur_str)
