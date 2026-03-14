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
        Returns a flat dict of user-chosen values.
        """
        params = self.config.get("parameters", {})
        exec_params = params.get("execution", {})
        coint_thresh = params.get("cointegration_thresholds", {})
        z_thresh = params.get("zscore_thresholds", {})

        with st.expander("⚙️ Step 1: Define Rules & Capital", expanded=True):
            st.markdown("Before calculating any math, we need to define the environment constraints.")
            c1, c2, c3 = st.columns(3)

            with c1:
                st.markdown("**Execution Costs**")
                capital = st.number_input(
                    "Total Capital Allocation ($)", 
                    min_value=100.0, 
                    value=float(exec_params.get("capital", 10000.0)),
                    step=1000.0, key="phase1_capital"
                )
                fee_rate_pct = st.number_input(
                    "Exchange Fee Rate (%)", 
                    min_value=0.0, 
                    value=float(exec_params.get("fee_rate_pct", 0.05)),
                    step=0.01, key="phase1_fee"
                )
                slippage_pct = st.number_input(
                    "Slippage (%)", 
                    min_value=0.0, 
                    value=float(exec_params.get("slippage_pct", 0.02)),
                    step=0.01, key="phase1_slippage"
                )

            with c2:
                st.markdown("**Statistical Windows**")
                coint_window = st.number_input(
                    "Cointegration Window (Bars)",
                    min_value=10,
                    value=int(params.get("cointegration_window", 180)),
                    help="How many bars to look back to calculate the OLS regression (Hedge Ratio).",
                    key="phase1_coint_window"
                )
                z_window = st.number_input(
                    "Z-Score MA Window (Bars)",
                    min_value=10,
                    value=int(params.get("zscore_window", 60)),
                    help="Smoothing window for the spread oscillator.",
                    key="phase1_z_window"
                )

            with c3:
                st.markdown("**Regime Filters (P-Value)**")
                coint_entry = st.number_input(
                    "Entry Barrier (Start Trading)",
                    min_value=0.01, max_value=1.0,
                    value=float(coint_thresh.get("entry", 0.10)),
                    step=0.01, key="phase1_coint_entry"
                )
                coint_cutoff = st.number_input(
                    "Emergency Cutoff (Kill Switch)",
                    min_value=0.05, max_value=1.0,
                    value=float(coint_thresh.get("cutoff", 0.70)),
                    step=0.01, key="phase1_coint_cutoff"
                )

            st.markdown("**Z-Score Triggers**")
            c4, c5 = st.columns(2)
            with c4:
                z_entry = st.number_input(
                    "Z-Score Entry",
                    min_value=1.0,
                    value=float(z_thresh.get("entry", 2.0)),
                    step=0.1, key="phase1_z_entry"
                )
            with c5:
                z_exit = st.number_input(
                    "Z-Score Exit",
                    min_value=-1.0,
                    value=float(z_thresh.get("exit", 0.0)),
                    step=0.1, key="phase1_z_exit"
                )

        return {
            "capital": capital,
            "fee_rate": fee_rate_pct / 100.0,
            "slippage": slippage_pct / 100.0,
            "coint_window": coint_window,
            "z_window": z_window,
            "coint_entry": coint_entry,
            "coint_cutoff": coint_cutoff,
            "z_entry": z_entry,
            "z_exit": z_exit,
        }

    def render_pipeline(self, st, df_pair: pd.DataFrame, asset_a: str, asset_b: str, params: Dict[str, Any]) -> None:
        """
        Renders the full Pairs Trading inspection pipeline (Phases 1–4).
        """
        from src.strategies.pairs.components.render_raw_data import plot_raw_normalized_prices
        from src.strategies.pairs.components.render_spread import plot_spread_and_regime
        from src.strategies.pairs.components.render_signals import render_zscore_and_signals
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
