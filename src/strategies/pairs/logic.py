import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional, Any
from src.engine.data.loader import DataLoader
from src.stats.cointegration import test_cointegration, calculate_rolling_spread, test_rolling_cointegration
from src.stats.zscore import calculate_z_score, generate_signals
import os
from src.engine.core.engine import VectorizedEngine

class PairsTradingStrategy:
    """
    Production Strategy Class for Pairs Trading / Auto-Screener.
    Responsible for:
    1. Taking a list of pre-filtered correlated pairs.
    2. Running rolling cointegration to ensure regime stability.
    3. Generating entry/exit signals based on Z-Scores out of the rolling spread.
    4. Passing the weights through VectorizedEngine to evaluate the edge.
    """
    
    def __init__(
        self, 
        timeframe: str = '1h',
        cointegration_window: int = 90,
        cointegration_p_value_threshold: float = 0.10,
        cointegration_cutoff_threshold: float = 0.40,
        zscore_window: int = 30,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.0,
        capital_per_pair: float = 10000.0,
        fee_rate: float = 0.0005,
        slippage: float = 0.0002
    ):
        self.timeframe = timeframe
        self.coint_window = cointegration_window
        self.coint_threshold = cointegration_p_value_threshold
        self.coint_cutoff = cointegration_cutoff_threshold
        self.zscore_window = zscore_window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.capital = capital_per_pair
        
        # Engine parameters for evaluation
        self.fee_rate = fee_rate
        self.slippage = slippage
        
    def evaluate_pair(self, asset_a: str, asset_b: str, prices: pd.DataFrame, basket_name: str = "Unknown") -> Dict[str, Any]:
        """
        Runs the full pipeline for a single pair:
        Math -> Signals -> Weights -> Engine Backtest
        
        Returns a dictionary of metrics if successful, or None if the pair failed to cointegrate.
        """
        df_pair = prices[[asset_a, asset_b]].ffill().dropna()
        if len(df_pair) < self.coint_window + self.zscore_window:
            return {'status': 'Insufficient Data'}
            
        # 1. Rolling Cointegration Math
        # Calculate the dynamic rolling spread and beta
        rolling_spread, rolling_beta = calculate_rolling_spread(df_pair[asset_a], df_pair[asset_b], window=self.coint_window)
        
        # Calculate the rolling P-Value to see if it is ACTUALLY mean-reverting
        _, raw_rolling_pval = test_rolling_cointegration(df_pair[asset_a], df_pair[asset_b], window=self.coint_window)
        
        # SMOOTHING (Combined Strategy Step 2): Apply a Moving Average to the p-value to remove 1-hour noise spikes
        pval_smoothing_window = 12
        numeric_pval = pd.to_numeric(raw_rolling_pval, errors='coerce')
        rolling_pval = numeric_pval.rolling(window=pval_smoothing_window).mean()
        
        # Sanity check: If the smoothed p-value never cointegrated in the entire out-of-sample period, reject it early
        if rolling_pval.min() > self.coint_threshold:
            return {'status': 'Never Cointegrated'}
            
        # 2. Z-Score Calculation
        z_score = calculate_z_score(rolling_spread, window=self.zscore_window)
        
        # 3. Signal Generation
        signals_df = generate_signals(z_score, entry_threshold=self.entry_threshold, exit_threshold=self.exit_threshold)
        
        # Regimes & Hysteresis (Combined Strategy Step 4):
        # We need to filter positions based on the smoothed p-value regime.
        positions = signals_df['position'].copy()
        
        # Align pval to positions
        aligned_pval = rolling_pval.reindex(positions.index).ffill()
        
        # Hysteresis Logic implementation without loops (using Pandas Vector tricks):
        # 1. Coint Cut-Off (Emergency Exit): If p-value goes completely crazy, force exit.
        regime_broken_mask = aligned_pval > self.coint_cutoff
        
        # 2. Coint Entry Barrier: If we are flat (0), we cannot enter unless p-value < coint_threshold (0.10).
        # We find where signals_df ATTEMPTED to enter a new position
        attempted_entries = (positions != 0) & (positions.shift(1).fillna(0) == 0)
        invalid_entries_mask = attempted_entries & (aligned_pval > self.coint_threshold)
        
        # To handle the case where we invalidate an entry, we must also nullify the position 
        # until the next valid exit or a new valid entry. In pure vectorization, this means 
        # forcing the position to 0 where the regime is broken OR where we tried to enter illegally.
        # Note: A true state machine would be better here, but for vectorized speed:
        
        # Apply the emergency cutoff
        positions.loc[regime_broken_mask] = 0.0
        
        # Instead of fully tracking the nullified state, let's use a simpler approach:
        # We just mute the position on the EXACT bars where entry is illegal. The generate_signals
        # logic already holds the '1' or '-1' state. If we mute it here, we are effectively saying 
        # "you can't hold a position while the p-val is > threshold AND you just tried to enter".
        # A more rigorous historical fix requires iterating, but let's approximate:
        # Let's apply the entry filter: if you were flat, and try to enter on bad p-val, stay flat.
        
        # Create a state machine series to fix the invalid entries cascading
        positions_fixed = []
        current_pos = 0.0
        
        for idx, pos in positions.items():
            pval = aligned_pval.loc[idx]
            
            # Emergency Cutoff overrides everything
            if pval > self.coint_cutoff:
                current_pos = 0.0
                positions_fixed.append(0.0)
                continue
                
            # Entry Attempt (Transition from 0 to non-zero)
            if current_pos == 0.0 and pos != 0.0:
                if pval <= self.coint_threshold:
                    current_pos = pos # Valid Entry
                else:
                    current_pos = 0.0 # Invalid Entry, block it
            # Exit Signal
            elif current_pos != 0.0 and pos == 0.0:
                current_pos = 0.0
            # Flip Position (Long to Short directly)
            elif current_pos != 0.0 and pos != current_pos and pos != 0.0:
                 if pval <= self.coint_threshold:
                     current_pos = pos
                 else:
                     current_pos = 0.0 # Block the flip, go flat
            
            positions_fixed.append(current_pos)
            
        positions = pd.Series(positions_fixed, index=positions.index)
        
        # 4. Generate Target Weights for the Engine
        weights = pd.DataFrame(0.0, index=df_pair.index, columns=df_pair.columns)
        
        # Weight allocation logic:
        # We allocate self.capital to the long leg, and short the other leg by beta.
        # CRITICAL FIX: Beta is a ratio of UNITS, not CAPITAL.
        # To get the capital allocation ratio, we multiply Beta by (Price B / Price A)
        current_capital_ratio = rolling_beta * (df_pair[asset_b] / df_pair[asset_a])
        
        # To avoid continuous rebalancing and racking up fees block-by-block, 
        # we freeze this capital ratio exactly at the time the position is opened or flipped.
        position_switches = positions != positions.shift(1).fillna(0)
        frozen_capital_ratio = current_capital_ratio.where(position_switches).ffill()
        
        # Raw weights: +1 for A, -ratio for B
        raw_w_a = positions
        raw_w_b = positions * (-frozen_capital_ratio)
        
        # Normalize weights so that abs(W_a) + abs(W_b) <= 1.0 (No leverage)
        total_abs_weight = raw_w_a.abs() + raw_w_b.abs()
        # Avoid division by zero
        total_abs_weight = total_abs_weight.replace(0, 1.0)
        
        weights[asset_a] = raw_w_a / total_abs_weight
        weights[asset_b] = raw_w_b / total_abs_weight
        
        # Drop NAs
        weights = weights.fillna(0.0)
        
        # 5. Run VectorizedEngine
        engine = VectorizedEngine(initial_capital=self.capital, fee_rate=self.fee_rate, slippage=self.slippage)
        results = engine.run(df_pair, weights)
        
        # 6. Extract Metrics
        total_pnl = results['equity'].iloc[-1] - self.capital
        return_pct = (total_pnl / self.capital) * 100
        
        # Basic Sharpe (Annualized approx for crypto h)
        returns = results['equity'].pct_change().dropna()
        if len(returns) > 0 and returns.std() != 0:
            # Assuming 1h timeframe for annualization
            periods_per_year = 365 * 24
            sharpe = (returns.mean() / returns.std()) * (periods_per_year ** 0.5)
        else:
            sharpe = 0.0
            
        # Max Drawdown
        roll_max = results['equity'].cummax()
        drawdown = (results['equity'] - roll_max) / roll_max
        max_dd = drawdown.min() * 100
        
        # 7. Extract Detailed Trade History & Enrich with Indicators
        trade_log = engine.get_trade_history()
        
        if not trade_log.empty:
            # We enrich the raw trade log with our strategy-specific indicators 
            # at the exact moment of execution
            trade_dates = pd.to_datetime(trade_log['Date'])
            
            # We log 1.0 for Asset A (Base) and the actual Beta multiplier for Asset B
            frozen_beta = rolling_beta.where(position_switches).ffill()
            raw_beta = trade_dates.map(frozen_beta).round(3)
            
            # Use numpy where to assign 1.0 if the row's 'Asset' is asset_a, else use raw_beta
            trade_log['Hedge Ratio (Beta)'] = np.where(trade_log['Asset'] == asset_a, 1.000, raw_beta)
            trade_log['P-Value'] = trade_dates.map(aligned_pval).round(4)
            
            # Ensure output directory exists for AI programmatic access logs
            os.makedirs("src/data/cache", exist_ok=True)
            
            # --- GENERATE COMPREHENSIVE TEXT REPORT ---
            report_lines = []
            report_lines.append("="*60)
            report_lines.append(f" DEEP STRATEGY REPORT: PAIRS TRADING ({asset_a} / {asset_b})")
            report_lines.append("="*60)
            report_lines.append("\n[1] GENERAL METADATA")
            report_lines.append(f" - Basket Used:           {basket_name}")
            report_lines.append(f" - Timeframe:             {self.timeframe}")
            report_lines.append("\n[2] COINTEGRATION REGIME PARAMETERS")
            report_lines.append(f" - Cointegration Window:  {self.coint_window} bars")
            report_lines.append(f" - P-Value Entry Barrier: <= {self.coint_threshold:.2f} (Green Zone)")
            report_lines.append(f" - P-Value Emerg. Cutoff: >  {self.coint_cutoff:.2f} (Red Zone)")
            report_lines.append("\n[3] SIGNAL GENERATION PARAMETERS (Z-SCORE)")
            report_lines.append(f" - Z-Score MA Window:     {self.zscore_window} bars")
            report_lines.append(f" - Z-Score Entry Trigger: ±{self.entry_threshold:.2f}")
            report_lines.append(f" - Z-Score Exit Trigger:  {self.exit_threshold:.2f}")
            report_lines.append("\n[4] EXECUTION PARAMETERS")
            report_lines.append(f" - Capital Allocated:     ${self.capital:,.2f}")
            report_lines.append(f" - Exchange Fee Rate:     {self.fee_rate*100:.2f}%")
            report_lines.append(f" - Estimated Slippage:    {self.slippage*100:.2f}%")
            report_lines.append("\n[5] PERFORMANCE SUMMARY")
            trades_count = (trade_log['Action'] == 'BUY').sum() + (trade_log['Action'] == 'SELL').sum()
            report_lines.append(f" - Total Trades Executed: {trades_count}")
            report_lines.append(f" - Maximum Drawdown:      {max_dd:.2f}%")
            report_lines.append(f" - Sharpe Ratio:          {sharpe:.2f}")
            report_lines.append(f" - Final Return:          {return_pct:.2f}%")
            
            report_lines.append("\n[6] DETAILED TRADE LOG & INDICATOR SNAPSHOTS")
            report_lines.append("-"*60)
            # Create a string representation of the DataFrame for the report
            df_str = trade_log.to_string(index=False)
            report_lines.append(df_str)
            report_lines.append("\n" + "="*60 + "\n")
            
            report_text = "\n".join(report_lines)
            
        else:
            report_text = "No trades were executed. No report generated."
            
        return {
            'status': 'Success',
            'asset_a': asset_a,
            'asset_b': asset_b,
            'total_return_pct': return_pct,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_dd,
            'latest_hedge_ratio': rolling_beta.iloc[-1] if not pd.isna(rolling_beta.iloc[-1]) else 0.0,
            'latest_p_value': aligned_pval.iloc[-1] if not pd.isna(aligned_pval.iloc[-1]) else 1.0,
            'final_equity': results['equity'].iloc[-1],
            'results_df': results,
            'trade_log': trade_log,
            'report_text': report_text
        }
