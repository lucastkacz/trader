import pandas as pd
from typing import Dict, Tuple, Optional, Any
from src.engine.data.loader import DataLoader
from src.stats.cointegration import test_cointegration, calculate_rolling_spread, test_rolling_cointegration
from src.stats.zscore import calculate_z_score, generate_signals
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
        cointegration_p_value_threshold: float = 0.05,
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
        self.zscore_window = zscore_window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.capital = capital_per_pair
        
        # Engine parameters for evaluation
        self.fee_rate = fee_rate
        self.slippage = slippage
        
    def evaluate_pair(self, asset_a: str, asset_b: str, prices: pd.DataFrame) -> Dict[str, Any]:
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
        _, rolling_pval = test_rolling_cointegration(df_pair[asset_a], df_pair[asset_b], window=self.coint_window)
        
        # Sanity check: If it never cointegrated in the entire out-of-sample period, reject it early
        if rolling_pval.min() > self.coint_threshold:
            return {'status': 'Never Cointegrated'}
            
        # 2. Z-Score Calculation
        z_score = calculate_z_score(rolling_spread, window=self.zscore_window)
        
        # 3. Signal Generation
        signals_df = generate_signals(z_score, entry_threshold=self.entry_threshold, exit_threshold=self.exit_threshold)
        
        # Regime Filter: We only allow taking a NEW position if the current rolling P-Value is significant.
        # If P-Value > 0.05, we force the position signal to 0 (unless we are already in a trade and exiting)
        positions = signals_df['position'].copy()
        
        # Align pval to positions
        aligned_pval = rolling_pval.reindex(positions.index).ffill()
        
        # Filter regime: If we are flat (0) and pval is bad (>0.05), we cannot enter.
        # This requires iterating or a mask. Simplest mask:
        # We can't easily mask entries without breaking exits in vectorized format cleanly without state tracking.
        # For a pure vector screener, we approximate by forcing positions to 0 where pval is bad.
        # (This means we might exit early if regime breaks, which is a valid safety mechanism).
        positions.loc[aligned_pval > self.coint_threshold] = 0.0
        
        # 4. Generate Target Weights for the Engine
        weights = pd.DataFrame(0.0, index=df_pair.index, columns=df_pair.columns)
        
        # Weight allocation logic:
        # We allocate self.capital to the long leg, and short the other leg by beta
        # So weights are effectively raw positions sizing in absolute dollars for the Engine
        weights[asset_a] = positions
        weights[asset_b] = positions * (-rolling_beta)
        
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
        
        return {
            'status': 'Success',
            'asset_a': asset_a,
            'asset_b': asset_b,
            'total_return_pct': return_pct,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_dd,
            'latest_hedge_ratio': rolling_beta.iloc[-1] if not pd.isna(rolling_beta.iloc[-1]) else 0.0,
            'latest_p_value': aligned_pval.iloc[-1] if not pd.isna(aligned_pval.iloc[-1]) else 1.0,
            'final_equity': results['equity'].iloc[-1]
        }
