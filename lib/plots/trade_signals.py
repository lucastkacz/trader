import plotly.graph_objects as go
import pandas as pd
from typing import List, Tuple

def add_trade_signals_traces(
    fig: go.Figure,
    z_score: pd.Series,
    long_entries: List[Tuple],
    short_entries: List[Tuple],
    exits: List[Tuple],
    symbol_a: str,
    symbol_b: str,
    entry_threshold: float = 2.0,
    stop_loss: float = 4.0,
    row: int = 1,
    col: int = 1
):
    """
    Adds trade signal traces (Z-score, markers, thresholds) to a specific subplot.
    """
    # 1. Z-Score Line
    fig.add_trace(go.Scatter(
        x=z_score.index.tolist(), 
        y=z_score.values,
        mode='lines', name='Z-Score',
        line=dict(color='#cfd8dc', width=1)
    ), row=row, col=col)

    # 2. Thresholds
    fig.add_hline(y=entry_threshold, line_dash="dash", line_color="red", annotation_text="Short Entry", row=row, col=col)
    fig.add_hline(y=-entry_threshold, line_dash="dash", line_color="green", annotation_text="Long Entry", row=row, col=col)
    fig.add_hline(y=0, line_color="gray", annotation_text="Mean (Exit)", row=row, col=col)
    fig.add_hline(y=stop_loss, line_dash="dot", line_color="darkred", annotation_text="Stop Loss", row=row, col=col)
    fig.add_hline(y=-stop_loss, line_dash="dot", line_color="darkred", annotation_text="Stop Loss", row=row, col=col)

    # 3. Markers
    if long_entries:
        l_x, l_y = zip(*long_entries)
        fig.add_trace(go.Scatter(
            x=l_x, y=l_y, mode='markers', name=f"LONG Spread (Buy {symbol_a} / Sell {symbol_b})",
            marker=dict(symbol='triangle-up', color='#00e676', size=12)
        ), row=row, col=col)

    if short_entries:
        s_x, s_y = zip(*short_entries)
        fig.add_trace(go.Scatter(
            x=s_x, y=s_y, mode='markers', name=f"SHORT Spread (Sell {symbol_a} / Buy {symbol_b})",
            marker=dict(symbol='triangle-down', color='#ff1744', size=12)
        ), row=row, col=col)
        
    if exits:
        e_x, e_y = zip(*exits)
        fig.add_trace(go.Scatter(
            x=e_x, y=e_y, mode='markers', name="Exit Position",
            marker=dict(symbol='circle-open', color='yellow', size=10, line=dict(width=2))
        ), row=row, col=col)

def plot_trade_signals(
    symbol_a: str, 
    symbol_b: str, 
    z_score: pd.Series, 
    long_entries: List[Tuple], 
    short_entries: List[Tuple], 
    exits: List[Tuple], 
    half_life: float,
    entry_threshold: float = 2.0,
    stop_loss: float = 4.0,
    extra_info: str = ""
):
    """
    Creates an interactive Plotly chart for Trading Signals.
    """
    fig = go.Figure()

    add_trade_signals_traces(
        fig, z_score, long_entries, short_entries, exits, 
        symbol_a, symbol_b, entry_threshold, stop_loss
    )

    # Title Logic
    title_text = f"Z-Score Signals: {symbol_a} vs {symbol_b} (Half-Life: {half_life:.1f}h)"
    if extra_info:
        title_text += f" | {extra_info}"

    fig.update_layout(
        title=title_text,
        template="plotly_dark",
        yaxis_title="Z-Score",
        xaxis_title="Date",
        height=600,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    fig.show()