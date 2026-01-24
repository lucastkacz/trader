import pandas as pd
import numpy as np
from typing import List, Dict

def calculate_backtest_stats(
    equity_curve: pd.Series, 
    trades: List[Dict],
    total_fees: float,
    initial_capital: float
) -> dict:
    """
    Calculates detailed performance metrics.
    """
    if equity_curve.empty:
        return {}
        
    end_val = equity_curve.iloc[-1]
    
    # --- Equity Metrics ---
    total_return = (end_val - initial_capital) / initial_capital
    
    returns = equity_curve.pct_change().dropna()
    ann_factor = np.sqrt(365 * 24)
    
    sharpe = 0.0
    if returns.std() > 0:
        sharpe = (returns.mean() / returns.std()) * ann_factor
        
    running_max = equity_curve.cummax()
    drawdowns = (equity_curve - running_max) / running_max
    max_drawdown = drawdowns.min()
    
    # --- Trade Metrics ---
    num_trades = len(trades)
    win_rate = 0.0
    profit_factor = 0.0
    avg_trade_pnl = 0.0
    best_trade = 0.0
    worst_trade = 0.0
    avg_duration = 0.0
    
    if num_trades > 0:
        df_trades = pd.DataFrame(trades)
        wins = df_trades[df_trades['pnl'] > 0]
        losses = df_trades[df_trades['pnl'] <= 0]
        
        win_rate = len(wins) / num_trades
        
        gross_profit = wins['pnl'].sum()
        gross_loss = abs(losses['pnl'].sum())
        
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        else:
            profit_factor = float('inf') if gross_profit > 0 else 0.0
            
        avg_trade_pnl = df_trades['return'].mean()
        best_trade = df_trades['return'].max()
        worst_trade = df_trades['return'].min()
        avg_duration = df_trades['duration'].mean()

    stats = {
        "Total Return": f"{total_return:.2%}",
        "Net Profit": f"${end_val - initial_capital:.2f}",
        "Sharpe Ratio": f"{sharpe:.2f}",
        "Max Drawdown": f"{max_drawdown:.2%}",
        "Total Fees": f"${total_fees:.2f}",
        "---": "---",
        "Total Trades": f"{num_trades}",
        "Win Rate": f"{win_rate:.1%}",
        "Profit Factor": f"{profit_factor:.2f}",
        "Avg Trade Return": f"{avg_trade_pnl:.2%}",
        "Best Trade": f"{best_trade:.2%}",
        "Worst Trade": f"{worst_trade:.2%}",
        "Avg Duration": f"{avg_duration:.1f} hrs"
    }
    
    return stats