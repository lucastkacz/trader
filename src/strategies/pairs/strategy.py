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
        """Placeholder for step-by-step rebuild"""
        return None, {}
        
    def evaluate(self, prices: pd.DataFrame, asset_a: str, asset_b: str = None, basket_name: str = "Unknown") -> Dict[str, Any]:
        """
        Clean Slate. We will build the logic here step by step.
        """
        return {
            'status': 'Clean Slate',
            'asset_a': asset_a,
            'asset_b': asset_b,
            'results_df': None,
            'trade_log': pd.DataFrame(),
            'report_text': "Strategy is currently a clean slate. Ready to build."
        }
