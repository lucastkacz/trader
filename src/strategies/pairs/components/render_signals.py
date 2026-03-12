import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.stats.zscore import calculate_z_score, generate_signals

def render_zscore_and_signals(spread: pd.Series, smoothed_p_values: pd.Series, z_window: int, z_entry: float, z_exit: float, coint_entry: float, coint_cutoff: float):
    """
    Renders Phase 3: Signal Generation Workspace.
    Normalizes the raw spread into a Z-Score and applies the regime 
    filter (P-Value) to generate actionable long/short trade signals.
    """
    if spread is None or spread.empty:
        return None
        
    st.markdown("### 🎯 Z-Score Oscillator & Trade Signals")
    st.markdown(
        f"We now take the Raw Spread from Phase 2 and normalize it using a `{z_window}` period Moving Average and Standard Deviation. "
        "This creates a **Z-Score Oscillator** centered around `0`. We only take trades when the spread deviates significantly "
        f"(±`{z_entry}`) AND the Cointegration Regime Filter (P-Value) is valid."
    )
    
    with st.spinner("Normalizing Spread and Generating State Machine Signals..."):
        # 1. Z-Score Calculation
        z_score = calculate_z_score(spread, window=z_window)
        
        # We need to align the smoothed p-value (which might have its own NaNs) to the exact timeframe of the z_score
        aligned_pval = smoothed_p_values.reindex(z_score.index).ffill()
        
        # Set up regime filters
        is_valid_entry = aligned_pval <= coint_entry
        is_force_exit = aligned_pval > coint_cutoff
        
        # Generate raw position states (-1, 0, 1)
        signals_df = generate_signals(
            z_score, 
            entry_threshold=z_entry, 
            exit_threshold=z_exit,
            is_valid_entry=is_valid_entry,
            is_force_exit=is_force_exit
        )
        
    # --- PLOT 1: Z-SCORE WITH THREE-ZONE REGIME BACKGROUND ---
    # Zones (determined by coint P-Value):
    #   🟢 Green  — pval <= coint_entry   : strong cointegration, entries allowed
    #   🟡 Amber  — coint_entry < pval <= coint_cutoff : caution, no new entries
    #   🔴 Red    — pval > coint_cutoff   : regime broken, force-exit
    fig = go.Figure()

    COLORS = {
        "green":  "rgba(67, 160, 71,  0.15)",   # #43A047
        "yellow": "rgba(255, 193, 7, 0.12)",    # amber
        "red":    "rgba(229, 57, 53,  0.18)",   # #E53935
    }

    def _classify(pval):
        if pval <= coint_entry:
            return "green"
        elif pval <= coint_cutoff:
            return "yellow"
        else:
            return "red"

    # Per-bar background shading — one rect per data bar, exactly matching the
    # bar-by-bar coloring in the Phase 2 P-Value chart.
    # The segment approach misses rapid zone oscillations (sub-1-bar thick rectangles
    # are nearly invisible). Here we replicate the bar chart method directly.
    regime_shapes = []
    bar_dur = (spread.index[1] - spread.index[0]) if len(spread.index) > 1 else pd.Timedelta(hours=1)

    # Gray warm-up band (p_values not yet available — mirrors gray bars in Phase 2)
    warm_up_bars = aligned_pval[aligned_pval.isna()].index
    if len(warm_up_bars):
        regime_shapes.append(dict(
            type="rect", xref="x", yref="paper",
            x0=warm_up_bars[0], x1=warm_up_bars[-1] + bar_dur,
            y0=0, y1=1,
            fillcolor="rgba(80,80,80,0.25)", layer="below", line_width=0,
        ))

    # One colored shape per valid bar
    valid = aligned_pval.dropna()
    for idx, pval in valid.items():
        regime_shapes.append(dict(
            type="rect", xref="x", yref="paper",
            x0=idx, x1=idx + bar_dur,
            y0=0, y1=1,
            fillcolor=COLORS[_classify(pval)], layer="below", line_width=0,
        ))

    # Z-Score line — added FIRST so Plotly correctly infers the datetime x-axis
    fig.add_trace(go.Scatter(
        x=z_score.index, y=z_score,
        name="Z-Score",
        line=dict(color='#FFA726', width=1.5),
    ))

    # Invisible dummy traces → legend entries for the three regime zones
    # (added AFTER the dated trace so axis type is already established)
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode='markers', name=f"🟢 Valid entry (p ≤ {coint_entry})",
        marker=dict(size=10, color="rgba(67,160,71,0.6)", symbol="square"),
    ))
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode='markers', name=f"🟡 Caution ({coint_entry} < p ≤ {coint_cutoff})",
        marker=dict(size=10, color="rgba(255,193,7,0.6)", symbol="square"),
    ))
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode='markers', name=f"🔴 Broken (p > {coint_cutoff})",
        marker=dict(size=10, color="rgba(229,57,53,0.6)", symbol="square"),
    ))

    # Entry/Exit threshold lines
    fig.add_hline(y=z_entry,  line_dash="dash", line_color="#E53935", annotation_text=f"Short Spread (+{z_entry})")
    fig.add_hline(y=-z_entry, line_dash="dash", line_color="#43A047", annotation_text=f"Long Spread (-{z_entry})")
    fig.add_hline(y=0,        line_dash="dot",  line_color="#757575", annotation_text="Mean (0)")

    # Entry / Exit markers
    positions        = signals_df['position']
    position_changes = positions.diff().fillna(0)

    enters_long  = z_score[(position_changes == 1)  & (positions ==  1)]
    enters_short = z_score[(position_changes == -1) & (positions == -1)]
    exits        = z_score[(position_changes != 0)  & (positions ==  0)]

    fig.add_trace(go.Scatter(
        x=enters_long.index, y=enters_long, mode='markers', name='Entry Long',
        marker=dict(symbol='triangle-up',   size=10, color='#00E676', line=dict(width=1, color='white')),
    ))
    fig.add_trace(go.Scatter(
        x=enters_short.index, y=enters_short, mode='markers', name='Entry Short',
        marker=dict(symbol='triangle-down', size=10, color='#FF1744', line=dict(width=1, color='white')),
    ))
    fig.add_trace(go.Scatter(
        x=exits.index, y=exits, mode='markers', name='Exit/Close',
        marker=dict(symbol='x', size=8, color='#BDBDBD'),
    ))

    fig.update_layout(
        title="Normalized Spread (Z-Score) & Trading Signals",
        height=480,
        hovermode="x unified",
        template="plotly_dark",
        shapes=regime_shapes,
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Display some basic stats about the signals
    c1, c2, c3, c4 = st.columns(4)
    total_trades = len(enters_long) + len(enters_short)
    current_position = positions.iloc[-1]
    
    status_text = "FLAT"
    if current_position == 1: status_text = "LONG SPREAD"
    elif current_position == -1: status_text = "SHORT SPREAD"
    
    c1.metric("Historical Trades Triggered", total_trades)
    c2.metric("Current Regime State", "INVALID" if aligned_pval.iloc[-1] > coint_cutoff else "VALID")
    c3.metric("Current Z-Score", f"{z_score.iloc[-1]:.2f}" if not pd.isna(z_score.iloc[-1]) else "N/A")
    c4.metric("Live Position Recommendation", status_text)

    return signals_df, z_score
