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
from src.strategies.factory import StrategyFactory

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
        self.capital = params.get("execution", {}).get("capital", 10000.0)
        
        # Engine parameters for evaluation
        execution_params = params.get("execution", {})
        self.fee_rate = execution_params.get("fee_rate_pct", 0.05) / 100.0
        self.slippage = execution_params.get("slippage_pct", 0.02) / 100.0
        
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

    # ------------------------------------------------------------------
    # Dashboard UI — Strategy-Owned Parameters & Pipeline
    # ------------------------------------------------------------------

    def render_parameters(self, st) -> Dict[str, Any]:
        """
        Renders parameter widgets, reading defaults from config.yml.
        Delegates to the dedicated parameters module.
        """
        from src.strategies.pairs.parameters import render_parameters as _render
        return _render(self.config, st)

    def render_pipeline(self, st, df_pair: pd.DataFrame, asset_a: str, asset_b: str, params: Dict[str, Any]) -> None:
        """
        Renders the full Pairs Trading inspection pipeline (Phases 1–4).
        """
        from src.strategies.pairs.components.render_raw_data import plot_raw_normalized_prices
        from src.strategies.pairs.components.render_spread import plot_spread_and_regime
        from src.strategies.pairs.components.render_signals import render_zscore_and_signals
        from src.strategies.pairs.components.render_trade_overlay import plot_price_with_trades
        from src.strategies.pairs.components.render_engine import render_engine_execution

        # --- Phase 1: Raw Data ---
        st.markdown("### 📊 Raw Asset Correlation")
        st.markdown(f"Fetching deep historical data for **{asset_a}** and **{asset_b}**...")
        plot_raw_normalized_prices(df_pair, asset_a, asset_b)

        st.divider()

        # --- Phase 2: Spread & Statistical Core ---
        st.header("Phase 2: Spread & Statistical Core")
        spread, smoothed_p_values, rolling_beta = plot_spread_and_regime(
            df_pair, asset_a, asset_b,
            coint_window=params["coint_window"],
            coint_entry=params["coint_entry"],
            coint_cutoff=params["coint_cutoff"],
        )

        if spread is None:
            return

        st.divider()

        # --- Phase 3: Signal Generation ---
        st.header("Phase 3: Signal Generation")
        result = render_zscore_and_signals(
            spread, smoothed_p_values,
            z_window=params["z_window"],
            z_entry=params["z_entry"],
            z_exit=params["z_exit"],
            coint_entry=params["coint_entry"],
            coint_cutoff=params["coint_cutoff"],
        )

        if result is None:
            return
        signals_df, z_score = result

        st.divider()

        # --- Phase 3b: Trade Overlay on Prices ---
        st.markdown("### 📍 Trade Overlay on Normalized Prices")
        st.markdown(
            "The same normalized price chart from Phase 1, now annotated with trade entries and exits "
            "from the signal generator. Shaded regions show when a trade is active."
        )
        plot_price_with_trades(df_pair, signals_df, z_score, asset_a, asset_b)

        st.divider()

        # --- Phase 4: Execution Engine ---
        st.header("Phase 4: Execution Engine & Weights")
        render_engine_execution(
            df_pair=df_pair,
            signals_df=signals_df,
            rolling_beta=rolling_beta,
            asset_a=asset_a,
            asset_b=asset_b,
            capital=params["capital"],
            fee_rate=params["fee_rate"],
            slippage=params["slippage"],
        )

        st.divider()
