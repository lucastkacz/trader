import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from src.stats.zscore import calculate_z_score, generate_signals

def render_signal_gen(spread: pd.Series, p_values: pd.Series, z_window: int, z_entry: float, z_exit: float):
    """
    Renders Module 3: Signal Generation.
    Takes the raw spread, calculates the rolling Z-Score, applies the entry/exit thresholds,
    AND applies the Regime Filter (P-value <= 0.05) to generate the final trading signals.
    Visualizes the Z-score with trigger points.
    """
    st.write("### 🚦 Module 3: Signal Generation")
    st.markdown(
        "Translating the raw spread into actionable trades using a **Rolling Z-Score**. "
        f"If the Z-Score crosses ±{z_entry} (and the pair is currently cointegrated), a trade is entered. "
        f"The trade is exited when it crosses {z_exit}."
    )
    
    if spread.empty:
        st.warning("No spread data available.")
        return None

    with st.spinner("Calculating Z-Scores & Signals..."):
        # 1. Math
        z_score = calculate_z_score(spread, window=z_window)
        signals = generate_signals(z_score, entry_threshold=z_entry, exit_threshold=z_exit)
        
        # 2. Apply Regime Filter
        # If P-value > 0.05, force position to 0 (no trade / exit)
        is_cointegrated = p_values <= 0.05
        # Align indices (p_values might have NaNs at the start)
        is_coint_aligned = is_cointegrated.reindex(signals.index).fillna(False)
        
        # Apply the filter natively to the positions
        # If not cointegrated, forced exit. 
        # (This is simplified for visualization; the actual Engine does strict path-dependent tracking, 
        # but for the chart we can show the exact blocks where trading is valid).
        filtered_position = signals['position'].where(is_coint_aligned, 0.0)
        signals['filtered_position'] = filtered_position

    # 3. Visualization
    fig = go.Figure()
    
    # Base Z-Score Line
    fig.add_trace(go.Scatter(
        x=z_score.index,
        y=z_score,
        name="Z-Score",
        line=dict(color='#82B1FF', width=1.5)
    ))
    
    # Threshold Lines
    fig.add_hline(y=z_entry, line_dash="dash", line_color="#FF3D00", annotation_text="Short Spread Entry")
    fig.add_hline(y=-z_entry, line_dash="dash", line_color="#00E676", annotation_text="Long Spread Entry")
    fig.add_hline(y=z_exit, line_dash="solid", line_color="#E0E0E0", annotation_text="Exit", opacity=0.5)

    # Highlight Regimes where trading is disabled (P-Value > 0.05)
    # We can plot a shaded background for invalid regimes, or just rely on the signals.
    # Let's plot actual Long / Short Entry signals as dots to make it highly visual.
    
    # Find points where position changed from 0 to 1 (Long Entry)
    long_entries = signals[(signals['filtered_position'] == 1) & (signals['filtered_position'].shift(1) != 1)]
    if not long_entries.empty:
        fig.add_trace(go.Scatter(
            x=long_entries.index,
            y=z_score.loc[long_entries.index],
            mode='markers',
            name='Enter Long (Buy A, Sell B)',
            marker=dict(color='#00E676', size=10, symbol='triangle-up')
        ))

    # Find points where position changed from 0 to -1 (Short Entry)
    short_entries = signals[(signals['filtered_position'] == -1) & (signals['filtered_position'].shift(1) != -1)]
    if not short_entries.empty:
        fig.add_trace(go.Scatter(
            x=short_entries.index,
            y=z_score.loc[short_entries.index],
            mode='markers',
            name='Enter Short (Sell A, Buy B)',
            marker=dict(color='#FF3D00', size=10, symbol='triangle-down')
        ))
        
    # Exits (Position went to 0 from non-zero)
    exits = signals[(signals['filtered_position'] == 0) & (signals['filtered_position'].shift(1).isin([1, -1]))]
    if not exits.empty:
        fig.add_trace(go.Scatter(
            x=exits.index,
            y=z_score.loc[exits.index],
            mode='markers',
            name='Exit Trade',
            marker=dict(color='#E0E0E0', size=8, symbol='x')
        ))

    fig.update_layout(
        title="Rolling Z-Score & Trade Triggers",
        yaxis_title="Z-Score",
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 4. Signal History Table
    st.write("#### Signal History Log")
    st.markdown("A definitive list of all signals fired by crossing the thresholds during valid cointegration regimes.")
    
    # Reconstruct exact events
    pos_changes = signals[signals['filtered_position'] != signals['filtered_position'].shift(1)]
    # Ignore the very first NaN to 0 transition
    pos_changes = pos_changes.iloc[1:]
    
    if pos_changes.empty:
        st.info("No trades were triggered by these parameters.")
    else:
        history = []
        for idx, row in pos_changes.iterrows():
            p = row['filtered_position']
            if p == 1.0: action = "🟢 Enter Long Spread"
            elif p == -1.0: action = "🔴 Enter Short Spread"
            else: action = "⚪ Exit Position"
            
            history.append({
                "Date": idx.strftime("%Y-%m-%d %H:%M"),
                "Action": action,
                "Z-Score at Signal": round(z_score.loc[idx], 2)
            })
            
        history_df = pd.DataFrame(history)
        st.dataframe(history_df, use_container_width=True, hide_index=True)
    
    return signals
