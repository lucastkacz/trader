import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

def add_equity_curve_traces(
    fig: go.Figure,
    equity_df: pd.DataFrame,
    symbol_a: str,
    symbol_b: str,
    initial_capital: float,
    row: int = 1,
    col: int = 1
):
    """Adds equity curve and benchmarks to the figure."""
    # 1. Equity Curve
    fig.add_trace(go.Scatter(
        x=equity_df.index, y=equity_df['equity'],
        mode='lines', name='Strategy Equity',
        line=dict(color='#00e676', width=2)
    ), row=row, col=col)
    
    # 2. Benchmarks (Normalized)
    if not equity_df.empty:
        start_price_a = equity_df['price_a'].iloc[0]
        start_price_b = equity_df['price_b'].iloc[0]
        
        bench_a = (equity_df['price_a'] / start_price_a) * initial_capital
        bench_b = (equity_df['price_b'] / start_price_b) * initial_capital
        
        fig.add_trace(go.Scatter(
            x=equity_df.index, y=bench_a,
            mode='lines', name=f'{symbol_a} (Hold)',
            line=dict(color='#29b6f6', width=1, dash='dot')
        ), row=row, col=col)
        
        fig.add_trace(go.Scatter(
            x=equity_df.index, y=bench_b,
            mode='lines', name=f'{symbol_b} (Hold)',
            line=dict(color='#ffa726', width=1, dash='dot')
        ), row=row, col=col)

def add_performance_table(
    fig: go.Figure,
    stats: dict,
    row: int = 1,
    col: int = 1
):
    """Adds a statistics table to the figure."""
    headers = ["Metric", "Value"]
    cells = [list(stats.keys()), list(stats.values())]
    
    fig.add_trace(go.Table(
        header=dict(
            values=headers,
            fill_color='#263238',
            align='left',
            font=dict(color='white', size=12)
        ),
        cells=dict(
            values=cells,
            fill_color='#37474f',
            align='left',
            font=dict(color='white', size=12),
            height=25
        )
    ), row=row, col=col)

def add_trade_history_table(
    fig: go.Figure,
    trades: list,
    row: int = 1,
    col: int = 1
):
    """Adds a detailed trade log table to the figure."""
    if not trades:
        return

    df = pd.DataFrame(trades)
    
    # Format Columns
    df['entry_time'] = pd.to_datetime(df['entry_time']).dt.strftime('%Y-%m-%d %H:%M')
    
    # Colors for PnL
    pnl_colors = ['#00e676' if x >= 0 else '#ff1744' for x in df['pnl']]
    
    # Prepare Table Data
    headers = [
        "Entry Time", "Type", "Long Leg", "Short Leg", 
        "Nominal ($)", "Fees ($)", "Max PnL ($)", "Min PnL ($)", "Net PnL ($)", "Dur (H)"
    ]
    
    cells = [
        df['entry_time'],
        df['type'],
        df['long_leg'],
        df['short_leg'],
        df['nominal_size'].map('${:,.0f}'.format),
        df['total_fees'].map('${:.2f}'.format),
        df['max_pnl'].map('${:.2f}'.format),
        df['min_pnl'].map('${:.2f}'.format),
        df['pnl'].map('${:,.2f}'.format),
        df['duration'].map('{:.1f}'.format)
    ]

    fig.add_trace(go.Table(
        header=dict(
            values=headers,
            fill_color='#263238',
            align='center',
            font=dict(color='white', size=11)
        ),
        cells=dict(
            values=cells,
            fill_color=['#37474f'] * 8 + [pnl_colors] + ['#37474f'], # Color the PnL column
            align='center',
            font=dict(color='white', size=11),
            height=25
        )
    ), row=row, col=col)

def plot_backtest_results(
    equity_df: pd.DataFrame, 
    stats: dict, 
    symbol_a: str, 
    symbol_b: str,
    initial_capital: float
):
    """
    Plots Equity Curve vs Individual Benchmarks and a Stats Table.
    """
    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.65, 0.35],
        specs=[[{"type": "xy"}], [{"type": "table"}]],
        vertical_spacing=0.08
    )
    
    add_equity_curve_traces(fig, equity_df, symbol_a, symbol_b, initial_capital, row=1, col=1)
    add_performance_table(fig, stats, row=2, col=1)
    
    fig.update_layout(
        title=f"Backtest Performance: {symbol_a} vs {symbol_b}",
        template="plotly_dark",
        height=900,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    fig.show()