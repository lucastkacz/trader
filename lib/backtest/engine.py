import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Union

class BacktestEngine:
    def __init__(self, initial_capital: float, fee_rate: float, slippage: float, leverage: float = 1.0):
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate
        self.slippage = slippage
        self.leverage = leverage
        self.trades = []
        self.total_fees = 0.0
        
    def run(self, 
            df1: pd.Series, 
            df2: pd.Series, 
            z_score: pd.Series, 
            hedge_ratio: Union[float, pd.Series], 
            entry_threshold: float, 
            exit_threshold: float, 
            stop_loss: float,
            symbol_a_name: str = "Asset A",
            symbol_b_name: str = "Asset B"
        ) -> Tuple[pd.DataFrame, List[Dict], float]:
        """
        Simulates the trading strategy.
        Returns: (Equity DataFrame, List of Trades, Total Fees Paid)
        """
        
        # Align data
        common_idx = df1.index.intersection(df2.index).intersection(z_score.index)
        
        if isinstance(hedge_ratio, pd.Series):
            common_idx = common_idx.intersection(hedge_ratio.index)
            hedge_ratio = hedge_ratio.loc[common_idx]
            
        df1 = df1.loc[common_idx]
        df2 = df2.loc[common_idx]
        z_score = z_score.loc[common_idx]
        
        cash = self.initial_capital
        position_a = 0.0
        position_b = 0.0
        in_position = 0 # 0: None, 1: Long, -1: Short
        
        # Trade Tracking
        trade_entry_equity = 0.0
        trade_entry_time = None
        trade_entry_fees = 0.0
        trade_nominal_size = 0.0
        trade_max_equity = -float('inf')
        trade_min_equity = float('inf')
        
        history = []
        
        for i in range(1, len(z_score)):
            ts = z_score.index[i]
            z = z_score.iloc[i]
            prev_z = z_score.iloc[i-1]
            p1 = df1.iloc[i]
            p2 = df2.iloc[i]
            
            # Determine Beta for this step
            if isinstance(hedge_ratio, pd.Series):
                current_beta = hedge_ratio.iloc[i]
            else:
                current_beta = hedge_ratio
                
            fee_cost = 0.0
            
            # --- Check Exits First ---
            if in_position != 0:
                should_exit = False
                exit_reason = ""
                
                if in_position == 1: # Long Spread
                    if z >= exit_threshold: 
                        should_exit = True
                        exit_reason = "Take Profit"
                    elif z <= -stop_loss: 
                        should_exit = True
                        exit_reason = "Stop Loss"
                        
                elif in_position == -1: # Short Spread
                    if z <= exit_threshold: 
                        should_exit = True
                        exit_reason = "Take Profit"
                    elif z >= stop_loss: 
                        should_exit = True
                        exit_reason = "Stop Loss"
                
                if should_exit:
                    # Close Positions
                    # Sell A
                    exec_p1 = p1 * (1 - self.slippage) if position_a > 0 else p1 * (1 + self.slippage)
                    val_a = position_a * exec_p1
                    f_a = abs(val_a) * self.fee_rate
                    cash += val_a - f_a
                    
                    # Buy B
                    exec_p2 = p2 * (1 + self.slippage) if position_b < 0 else p2 * (1 - self.slippage)
                    val_b = position_b * exec_p2
                    f_b = abs(val_b) * self.fee_rate
                    cash += val_b - f_b
                    
                    fee_cost += (f_a + f_b)
                    
                    # PnL Calculations
                    current_equity = cash
                    trade_pnl = current_equity - trade_entry_equity
                    trade_ret = trade_pnl / trade_entry_equity
                    
                    # Determine Leg Roles
                    long_leg = symbol_a_name if in_position == 1 else symbol_b_name
                    short_leg = symbol_b_name if in_position == 1 else symbol_a_name
                    
                    self.trades.append({
                        'entry_time': trade_entry_time,
                        'exit_time': ts,
                        'reason': exit_reason,
                        'type': 'Long Spread' if in_position == 1 else 'Short Spread',
                        'long_leg': long_leg,
                        'short_leg': short_leg,
                        'nominal_size': trade_nominal_size,
                        'total_fees': trade_entry_fees + fee_cost,
                        'pnl': trade_pnl,
                        'return': trade_ret,
                        'max_pnl': trade_max_equity - trade_entry_equity,
                        'min_pnl': trade_min_equity - trade_entry_equity,
                        'duration': (ts - trade_entry_time).total_seconds() / 3600
                    })
                    
                    position_a = 0.0
                    position_b = 0.0
                    in_position = 0

            # --- Check Entries ---
            if in_position == 0:
                signal = 0
                if z < -entry_threshold and prev_z >= -entry_threshold:
                    signal = 1 # Long Spread (Long A, Short B)
                elif z > entry_threshold and prev_z <= entry_threshold:
                    signal = -1 # Short Spread (Short A, Long B)
                    
                if signal != 0:
                    abs_beta = abs(current_beta)
                    
                    # Allocate capital
                    alloc_capital = cash * self.leverage
                    q_a = alloc_capital / (p1 + abs_beta * p2)
                    q_b = q_a * abs_beta
                    
                    if signal == 1:
                        position_a = q_a
                        position_b = -q_b
                        # Costs
                        exec_p1 = p1 * (1 + self.slippage)
                        exec_p2 = p2 * (1 - self.slippage)
                        in_position = 1
                        
                    elif signal == -1:
                        position_a = -q_a
                        position_b = q_b
                        # Costs
                        exec_p1 = p1 * (1 - self.slippage)
                        exec_p2 = p2 * (1 + self.slippage)
                        in_position = -1
                    
                    # Execute
                    cost_a = position_a * exec_p1
                    cost_b = position_b * exec_p2
                    
                    f_a = abs(cost_a) * self.fee_rate
                    f_b = abs(cost_b) * self.fee_rate
                    
                    cash -= (cost_a + f_a)
                    cash -= (cost_b + f_b)
                    
                    fee_cost += (f_a + f_b)
                    
                    # Record Entry State for PnL Calc
                    trade_entry_equity = cash + (position_a * p1) + (position_b * p2)
                    trade_entry_time = ts
                    trade_entry_fees = fee_cost
                    trade_nominal_size = abs(cost_a) + abs(cost_b)
                    
                    # Reset Peak Tracking
                    trade_max_equity = trade_entry_equity
                    trade_min_equity = trade_entry_equity

            self.total_fees += fee_cost

            # --- Mark to Market ---
            val_a = position_a * p1
            val_b = position_b * p2
            equity = cash + val_a + val_b
            
            # Track Intra-Trade Peaks
            if in_position != 0:
                if equity > trade_max_equity: trade_max_equity = equity
                if equity < trade_min_equity: trade_min_equity = equity
            
            history.append({
                'timestamp': ts,
                'equity': equity,
                'price_a': p1,
                'price_b': p2,
                'in_position': in_position
            })
            
        df_res = pd.DataFrame(history)
        if not df_res.empty:
            df_res = df_res.set_index('timestamp')
            
        return df_res, self.trades, self.total_fees