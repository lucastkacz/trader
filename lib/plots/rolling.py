import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

def add_rolling_stats_traces(fig: go.Figure, stats_df: pd.DataFrame, start_row: int = 1, col: int = 1):
    """
    Adds rolling statistics traces to an existing figure across 5 consecutive rows.
    
    Args:
        fig: The Plotly figure object.
        stats_df: DataFrame output from calculate_rolling_stats.
        start_row: The starting row index (1-based). Traces will use start_row to start_row+4.
        col: The column index.
    """
    if stats_df.empty:
        return

    # 1. Hedge Ratio
    fig.add_trace(go.Scatter(
        x=stats_df.index, y=stats_df['hedge_ratio'],
        name="Hedge Ratio", mode='lines', line=dict(color='#29b6f6')
    ), row=start_row, col=col)

    # 2. Correlation
    fig.add_trace(go.Scatter(
        x=stats_df.index, y=stats_df['correlation'],
        name="Correlation", mode='lines', line=dict(color='#26a69a')
    ), row=start_row + 1, col=col)
    
    # Add threshold line for Corr (e.g., 0.8)
    fig.add_hline(y=0.8, line_dash="dot", line_color="gray", row=start_row + 1, col=col)

    # 3. P-Value
    fig.add_trace(go.Scatter(
        x=stats_df.index, y=stats_df['p_value'],
        name="P-Value", mode='lines', line=dict(color='#ef5350')
    ), row=start_row + 2, col=col)
    
    # Critical Threshold (0.05)
    fig.add_hline(y=0.05, line_dash="dash", line_color="green", annotation_text="0.05 Sig", row=start_row + 2, col=col)

    # 4. Half-Life
    fig.add_trace(go.Scatter(
        x=stats_df.index, y=stats_df['half_life'],
        name="Half-Life", mode='lines', line=dict(color='#ffa726')
    ), row=start_row + 3, col=col)
    
    # Threshold (e.g. 24h)
    fig.add_hline(y=24, line_dash="dot", line_color="gray", row=start_row + 3, col=col)

    # 5. Hurst
    fig.add_trace(go.Scatter(
        x=stats_df.index, y=stats_df['hurst'],
        name="Hurst", mode='lines', line=dict(color='#ab47bc')
    ), row=start_row + 4, col=col)
    
    # Threshold (0.5)
    fig.add_hline(y=0.5, line_dash="dash", line_color="white", row=start_row + 4, col=col)

def plot_rolling_stats(stats_df: pd.DataFrame, title: str = "Rolling Analysis"):
    """
    Plots the evolution of pair statistics over time.
    """
    if stats_df.empty:
        print("No data to plot.")
        return

    # Create 5-row subplot
    fig = make_subplots(
        rows=5, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=("Hedge Ratio", "Correlation", "Cointegration P-Value", "Half-Life (Hours)", "Hurst Exponent"),
        row_heights=[0.2, 0.2, 0.2, 0.2, 0.2]
    )

    add_rolling_stats_traces(fig, stats_df, start_row=1, col=1)

    fig.update_layout(
        title=title,
        template="plotly_dark",
        height=1200,
        showlegend=False
    )
    
    fig.show()
