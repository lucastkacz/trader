import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import List, Tuple

from lib.plots.rolling import add_rolling_stats_traces
from lib.plots.trade_signals import add_trade_signals_traces
from lib.plots.performance import add_equity_curve_traces, add_performance_table, add_trade_history_table

def plot_unified_dashboard(
    symbol_a: str, 
    symbol_b: str,
    rolling_df: pd.DataFrame,
    z_score: pd.Series,
    long_entries: List[Tuple],
    short_entries: List[Tuple],
    exits: List[Tuple],
    equity_df: pd.DataFrame,
    stats: dict,
    trades: List[dict],
    half_life: float,
    initial_capital: float,
    z_thresholds: dict
):
    """
    Creates a unified dashboard by orchestrating sub-plots from other modules.
    
    Structure (9 Rows):
    1. Rolling Hedge Ratio
    2. Rolling Correlation
    3. Rolling P-Value
    4. Rolling Half-Life
    5. Rolling Hurst
    6. Trade Signals (Z-Score)
    7. Equity Curve
    8. Strategy Statistics
    9. Trade History Log
    """
    
    # 9 Rows
    fig = make_subplots(
        rows=9, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.08, 0.08, 0.08, 0.08, 0.08, 0.15, 0.15, 0.1, 0.2],
        subplot_titles=(
            "Rolling Hedge Ratio",
            "Rolling Correlation", 
            "Rolling P-Value", 
            "Rolling Half-Life", 
            "Rolling Hurst",
            f"Z-Score Signals (HL: {half_life:.1f}h)", 
            "Backtest Performance", 
            "Strategy Statistics",
            "Trade History Log"
        ),
        specs=[
            [{"type": "xy"}], # Rolling 1 (HR)
            [{"type": "xy"}], # Rolling 2 (Corr)
            [{"type": "xy"}], # Rolling 3 (P-Val)
            [{"type": "xy"}], # Rolling 4 (HL)
            [{"type": "xy"}], # Rolling 5 (Hurst)
            [{"type": "xy"}], # Signals
            [{"type": "xy"}], # Equity
            [{"type": "table"}], # Stats
            [{"type": "table"}]  # Log
        ]
    )

    # 1-5. Rolling Stats (Rows 1-5)
    add_rolling_stats_traces(fig, rolling_df, start_row=1, col=1)

    # 6. Trade Signals (Row 6)
    add_trade_signals_traces(
        fig, 
        z_score, 
        long_entries, 
        short_entries, 
        exits, 
        symbol_a, 
        symbol_b, 
        entry_threshold=z_thresholds.get('entry', 2.0), 
        stop_loss=4.0, 
        row=6, 
        col=1
    )

    # 7. Equity Curve (Row 7)
    add_equity_curve_traces(
        fig, 
        equity_df, 
        symbol_a, 
        symbol_b, 
        initial_capital, 
        row=7, 
        col=1
    )

    # 8. Stats Table (Row 8)
    add_performance_table(fig, stats, row=8, col=1)

    # 9. Trade Log (Row 9)
    add_trade_history_table(fig, trades, row=9, col=1)

    fig.update_layout(
        title=f"Quant Dashboard: {symbol_a} vs {symbol_b}",
        template="plotly_dark",
        height=2400, 
        showlegend=False
    )
    
    fig.show()
