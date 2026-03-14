import streamlit as st
import pandas as pd
import plotly.graph_objects as go


def plot_price_with_trades(
    df_pair: pd.DataFrame,
    signals_df: pd.DataFrame,
    z_score: pd.Series,
    asset_a: str,
    asset_b: str,
):
    """
    Renders a normalized price chart for both assets with trade entry/exit
    markers overlaid. Long-spread entries, short-spread entries, and exits
    are shown directly on the price canvas so the user can visually connect
    signal generation (Phase 3) with real price action.
    """
    if df_pair.empty or signals_df is None:
        return

    # ── Normalize prices to base 100 ─────────────────────────────────
    norm_a = (df_pair[asset_a] / df_pair[asset_a].iloc[0]) * 100
    norm_b = (df_pair[asset_b] / df_pair[asset_b].iloc[0]) * 100

    # ── Detect trade entry / exit timestamps ─────────────────────────
    positions = signals_df["position"]
    pos_diff = positions.diff().fillna(0)

    long_entry_idx  = pos_diff[(pos_diff ==  1) & (positions ==  1)].index
    short_entry_idx = pos_diff[(pos_diff == -1) & (positions == -1)].index
    exit_idx        = pos_diff[(pos_diff != 0)  & (positions ==  0)].index

    # ── Build round-trip spans for background shading ────────────────
    trip_spans = []
    entries = pos_diff[pos_diff != 0].index.tolist()
    current_dir = None
    current_open = None

    for ts in entries:
        pos = positions.loc[ts]
        if pos != 0 and current_dir is None:
            current_dir = "LONG SPREAD" if pos == 1 else "SHORT SPREAD"
            current_open = ts
        elif pos == 0 and current_dir is not None:
            trip_spans.append((current_open, ts, current_dir))
            current_dir = None
            current_open = None

    # ── Figure ───────────────────────────────────────────────────────
    fig = go.Figure()

    # Trade background bands (scatter fill, same technique as equity chart)
    y_lo = min(norm_a.min(), norm_b.min()) * 0.98
    y_hi = max(norm_a.max(), norm_b.max()) * 1.02

    for t_open, t_close, direction in trip_spans:
        band_color = "rgba(33, 150, 243, 0.12)" if direction == "LONG SPREAD" else "rgba(255, 152, 0, 0.12)"
        fig.add_trace(go.Scatter(
            x=[t_open, t_close, t_close, t_open, t_open],
            y=[y_lo,   y_lo,    y_hi,    y_hi,   y_lo],
            fill="toself",
            fillcolor=band_color,
            line=dict(width=0),
            mode="lines",
            showlegend=False,
            hoverinfo="skip",
        ))

    # Price lines
    fig.add_trace(go.Scatter(
        x=norm_a.index, y=norm_a,
        name=asset_a,
        line=dict(color="#00E676", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=norm_b.index, y=norm_b,
        name=asset_b,
        line=dict(color="#29B6F6", width=2),
    ))

    # ── Trade markers (placed on asset_a's normalized price) ─────────
    # Using asset_a as anchor point since it's the reference asset
    fig.add_trace(go.Scatter(
        x=long_entry_idx,
        y=norm_a.reindex(long_entry_idx),
        mode="markers",
        name="Entry Long Spread",
        marker=dict(
            symbol="triangle-up", size=12, color="#00E676",
            line=dict(width=1.5, color="white"),
        ),
    ))
    fig.add_trace(go.Scatter(
        x=short_entry_idx,
        y=norm_a.reindex(short_entry_idx),
        mode="markers",
        name="Entry Short Spread",
        marker=dict(
            symbol="triangle-down", size=12, color="#FF1744",
            line=dict(width=1.5, color="white"),
        ),
    ))
    fig.add_trace(go.Scatter(
        x=exit_idx,
        y=norm_a.reindex(exit_idx),
        mode="markers",
        name="Exit",
        marker=dict(
            symbol="x", size=10, color="#BDBDBD",
            line=dict(width=1.5, color="white"),
        ),
    ))

    # Legend dummies for band colors
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode="markers",
        name="🔵 Long Spread Trade",
        marker=dict(size=10, color="rgba(33,150,243,0.5)", symbol="square"),
    ))
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode="markers",
        name="🟠 Short Spread Trade",
        marker=dict(size=10, color="rgba(255,152,0,0.5)", symbol="square"),
    ))

    fig.update_layout(
        title="Normalized Prices with Trade Overlay",
        height=500,
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=40, r=40, t=60, b=40),
        yaxis=dict(title="Normalized Price Index", range=[y_lo, y_hi]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig, use_container_width=True)
