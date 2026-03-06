import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional, Any
from src.engine.data.loader import DataLoader
from src.stats.cointegration import test_cointegration, calculate_rolling_spread, test_rolling_cointegration
from src.stats.zscore import calculate_z_score, generate_signals
import os
from src.engine.core.engine import VectorizedEngine
from src.engine.core.logger import StrategyLogger
from src.strategies.base import BaseStrategy

class PairsTradingStrategy(BaseStrategy):
    """
    Production Strategy Class for Pairs Trading / Auto-Screener.
    Responsible for:
    1. Taking a list of pre-filtered correlated pairs.
    2. Running rolling cointegration to ensure regime stability.
    3. Generating entry/exit signals based on Z-Scores out of the rolling spread.
    4. Passing the weights through VectorizedEngine to evaluate the edge.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Load params from config
        params = self.config.get("parameters", {})
        
        self.timeframe = self.config.get("timeframe", "1h")
        self.coint_window = params.get("cointegration_window", 90)
        self.coint_threshold = params.get("cointegration_thresholds", {}).get("entry", 0.10)
        self.coint_cutoff = params.get("cointegration_thresholds", {}).get("cutoff", 0.40)
        self.zscore_window = params.get("zscore_window", 30)
        self.entry_threshold = params.get("zscore_thresholds", {}).get("entry", 2.0)
        self.exit_threshold = params.get("zscore_thresholds", {}).get("exit", 0.0)
        self.capital = params.get("capital_per_pair", 10000.0)
        
        # Engine parameters for evaluation
        execution_params = params.get("execution", {})
        self.fee_rate = execution_params.get("fee_rate", 0.0005)
        self.slippage = execution_params.get("slippage", 0.0002)
        
    @property
    def sort_ascending(self) -> bool:
        """Lower P-Value is better for Cointegration"""
        return True

    def get_screening_metric(self, prices: pd.DataFrame, asset_a: str, asset_b: str = None) -> Tuple[Optional[float], Dict[str, Any]]:
        """Runs rolling Engle-Granger tests to see if the pair meets the valid regime."""
        df_pair = prices[[asset_a, asset_b]].ffill().dropna()
        if len(df_pair) < self.coint_window:
            return None, {}
            
        _, rolling_beta = calculate_rolling_spread(df_pair[asset_a], df_pair[asset_b], window=self.coint_window)
        _, rolling_pval = test_rolling_cointegration(df_pair[asset_a], df_pair[asset_b], window=self.coint_window)
        
        valid_pvals = rolling_pval.dropna()
        if len(valid_pvals) > 0:
            latest_pval = float(valid_pvals.iloc[-1])
            latest_beta = float(rolling_beta.dropna().iloc[-1]) if len(rolling_beta.dropna()) > 0 else 0.0
            survived = bool(valid_pvals.min() <= self.coint_threshold)
            return latest_pval, {'hedge_ratio': latest_beta, 'survived': survived}
            
        return None, {}
        
    def evaluate(self, prices: pd.DataFrame, asset_a: str, asset_b: str = None, basket_name: str = "Unknown") -> Dict[str, Any]:
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
        
        # Align the smoothed p-value to the z_score index
        aligned_pval = rolling_pval.reindex(z_score.index).ffill()
        
        # Set up regime filters for the signal generator
        is_valid_entry = aligned_pval <= self.coint_threshold
        is_force_exit = aligned_pval > self.coint_cutoff
        
        # 3. Signal Generation (State machine handles regime logic natively now)
        signals_df = generate_signals(
            z_score, 
            entry_threshold=self.entry_threshold, 
            exit_threshold=self.exit_threshold,
            is_valid_entry=is_valid_entry,
            is_force_exit=is_force_exit
        )
        
        positions = signals_df['position'].copy()
        
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
            trade_log['Z-Score'] = trade_dates.map(z_score).round(3)
            
            # Ensure output directory exists for AI programmatic access logs
            os.makedirs("src/data/cache", exist_ok=True)
            
            # --- GENERATE COMPREHENSIVE TEXT REPORT ---
            trades_count = (trade_log['Action'] == 'BUY').sum() + (trade_log['Action'] == 'SELL').sum()
            time_in_market = results.attrs.get('time_in_market_pct', 0.0)
            
            parameters = {
                "Basket Used": basket_name,
                "Timeframe": self.timeframe,
                "Cointegration Window": f"{self.coint_window} bars",
                "P-Value Entry Barrier": f"<= {self.coint_threshold:.2f} (Green Zone)",
                "P-Value Emerg. Cutoff": f">  {self.coint_cutoff:.2f} (Red Zone)",
                "Z-Score MA Window": f"{self.zscore_window} bars",
                "Z-Score Entry Trigger": f"±{self.entry_threshold:.2f}",
                "Z-Score Exit Trigger": f"{self.exit_threshold:.2f}",
                "Capital Allocated": f"${self.capital:,.2f}",
                "Exchange Fee Rate": f"{self.fee_rate*100:.2f}%",
                "Estimated Slippage": f"{self.slippage*100:.2f}%"
            }
            
            performance = {
                "Total Trades Executed": trades_count,
                "Time in Market": f"{time_in_market:.2f}%",
                "Maximum Drawdown": f"{max_dd:.2f}%",
                "Sharpe Ratio": f"{sharpe:.2f}",
                "Final Return": f"{return_pct:.2f}%"
            }
            
            report_text = StrategyLogger.generate_report(
                strategy_name="Pairs Trading",
                asset_info=f"{asset_a} / {asset_b}",
                parameters=parameters,
                performance=performance,
                trade_log=trade_log
            )
            
        else:
            report_text = "No trades were executed. No report generated."
            time_in_market = 0.0
            
        return {
            'status': 'Success',
            'asset_a': asset_a,
            'asset_b': asset_b,
            'total_return_pct': return_pct,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_dd,
            'time_in_market_pct': time_in_market,
            'latest_hedge_ratio': rolling_beta.iloc[-1] if not pd.isna(rolling_beta.iloc[-1]) else 0.0,
            'latest_p_value': aligned_pval.iloc[-1] if not pd.isna(aligned_pval.iloc[-1]) else 1.0,
            'final_equity': results['equity'].iloc[-1],
            'results_df': results,
            'trade_log': trade_log,
            'report_text': report_text,
            'parameters': parameters if 'parameters' in locals() else {},
            'performance': performance if 'performance' in locals() else {}
        }
