import os
import json
import numpy as np
import pandas as pd
from itertools import product
from typing import Optional

from src.core.logger import logger
from src.data.storage.local_parquet import ParquetStorage
from src.simulation.vectorized_engine import Simulator
from src.simulation.friction_model import FrictionEngine
from src.utils.timeframe_math import get_bars_per_year

class StressTestOrchestrator:
    def __init__(self, storage: ParquetStorage):
        self.storage = storage

    def load_pairs(self, timeframe: str) -> list:
        path = f"data/universes/{timeframe}/surviving_pairs.json"
        if not os.path.exists(path):
            path = f"data/universes/{timeframe}/pairs.json"
        with open(path, "r") as f:
            return json.load(f)

    def build_unified_df(self, symbol_a: str, symbol_b: str, timeframe: str) -> Optional[pd.DataFrame]:
        try:
            df_a = self.storage.load_ohlcv(symbol_a, timeframe, exchange="bybit")
            df_b = self.storage.load_ohlcv(symbol_b, timeframe, exchange="bybit")
        except Exception as e:
            logger.warning(f"Failed loading parquet for {symbol_a}/{symbol_b}: {e}")
            return None

        df_a = df_a.set_index("timestamp").add_prefix("A_")
        df_b = df_b.set_index("timestamp").add_prefix("B_")

        merged = df_a.join(df_b, how="inner")

        if len(merged) < 500:
            logger.warning(f"Insufficient overlap for {symbol_a}/{symbol_b}: {len(merged)} bars")
            return None

        return merged

    def inject_volatility_parity(self, df: pd.DataFrame, vol_lookback_bars: int) -> pd.DataFrame:
        ret_a = np.log(df["A_close"] / df["A_close"].shift(1))
        ret_b = np.log(df["B_close"] / df["B_close"].shift(1))

        vol_a = ret_a.rolling(window=vol_lookback_bars, min_periods=vol_lookback_bars).std()
        vol_b = ret_b.rolling(window=vol_lookback_bars, min_periods=vol_lookback_bars).std()

        inv_a = 1.0 / vol_a
        inv_b = 1.0 / vol_b
        sum_inv = inv_a + inv_b

        df["weight_A"] = (inv_a / sum_inv).fillna(0.5)
        df["weight_B"] = (inv_b / sum_inv).fillna(0.5)

        return df

    def build_zscore(self, df: pd.DataFrame, lookback_bars: int) -> pd.DataFrame:
        log_a = np.log(df["A_close"])
        log_b = np.log(df["B_close"])

        spread = log_a - log_b

        rolling_mean = spread.rolling(window=lookback_bars, min_periods=lookback_bars).mean()
        rolling_std = spread.rolling(window=lookback_bars, min_periods=lookback_bars).std()

        rolling_std = rolling_std.replace(0.0, np.nan)
        df["z_score"] = (spread - rolling_mean) / rolling_std

        return df

    def run(self, timeframe: str, backtest_cfg: dict, strategy_cfg: dict):
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("  EPOCH 2: Vectorized Stress Test Orchestrator")
        logger.info("═══════════════════════════════════════════════════════════")

        grid_cfg = backtest_cfg["grid_search"]
        friction_cfg = backtest_cfg["friction"]
        
        entry_z_scores = grid_cfg["entry_z_scores"]
        lookback_bars_grid = grid_cfg["lookback_bars"]
        exit_z = strategy_cfg["execution"]["exit_z_score"]
        
        maker_fee = friction_cfg["maker_fee"]
        taker_fee = friction_cfg["taker_fee"]
        annual_fund_rate = friction_cfg["annual_fund_rate"]
        vol_lookback_bars = strategy_cfg["execution"]["volatility_lookback_bars"]

        bars_per_year = get_bars_per_year(timeframe)

        pairs = self.load_pairs(timeframe)
        logger.info(f"Loaded {len(pairs)} cointegrated pairs from Epoch 1.")

        sim = Simulator()
        friction = FrictionEngine(maker_fee=maker_fee, taker_fee=taker_fee, annual_fund_rate=annual_fund_rate)

        grid = list(product(lookback_bars_grid, entry_z_scores))
        logger.info(f"Grid Search: {len(grid)} parameter combinations per pair.")
        logger.info(f"Total simulations: {len(pairs) * len(grid)}")

        surviving_pairs = []

        for pair_idx, pair in enumerate(pairs):
            asset_x = pair["Asset_X"]
            asset_y = pair["Asset_Y"]
            pair_label = f"{asset_x} / {asset_y}"

            logger.info(f"[{pair_idx+1}/{len(pairs)}] Stress-testing: {pair_label}")

            unified = self.build_unified_df(asset_x, asset_y, timeframe)
            if unified is None:
                continue

            unified = self.inject_volatility_parity(unified, vol_lookback_bars)

            best_net_pnl = -np.inf
            best_params = None
            best_stats = None

            for lookback_bars, entry_z in grid:

                df = unified.copy()
                df = self.build_zscore(df, lookback_bars)

                df = df.dropna(subset=["z_score"]).reset_index(drop=True)
                if len(df) < 200:
                    continue

                gross_df = sim.run(df, entry_z=entry_z, exit_z=exit_z)

                gross_df["gross_returns"] = gross_df["position"] * (
                    gross_df["weight_A"] * gross_df["trade_ret_A"]
                    - gross_df["weight_B"] * gross_df["trade_ret_B"]
                )
                gross_df["gross_returns"] = gross_df["gross_returns"].fillna(0.0)

                net_df = friction.apply(gross_df)

                equity = net_df["net_returns"].cumsum()
                final_pnl = equity.iloc[-1] if len(equity) > 0 else -np.inf

                rolling_max = equity.cummax()
                drawdown = equity - rolling_max
                max_dd = drawdown.min()

                trades = (net_df["position"].diff().abs() > 0).sum()

                if net_df["net_returns"].std() > 0:
                    sharpe = (net_df["net_returns"].mean() / net_df["net_returns"].std()) * np.sqrt(bars_per_year)
                else:
                    sharpe = 0.0

                if final_pnl > best_net_pnl:
                    best_net_pnl = final_pnl
                    best_params = {"lookback_bars": lookback_bars, "entry_z": entry_z}
                    best_stats = {
                        "final_pnl_pct": round(final_pnl * 100, 4),
                        "max_drawdown_pct": round(max_dd * 100, 4),
                        "sharpe_ratio": round(sharpe, 4),
                        "total_trades": int(trades),
                        "bars_tested": len(net_df)
                    }

            if best_net_pnl > 0 and best_params is not None:
                surviving_pairs.append({
                    "Cohort": pair["Cohort"],
                    "Asset_X": asset_x,
                    "Asset_Y": asset_y,
                    "Hedge_Ratio": pair["Hedge_Ratio"],
                    "Half_Life": pair["Half_Life"],
                    "P_Value": pair["P_Value"],
                    "Best_Params": best_params,
                    "Performance": best_stats
                })
                logger.info(
                    f"  ✓ SURVIVED | PnL: {best_stats['final_pnl_pct']:.2f}% | "
                    f"Sharpe: {best_stats['sharpe_ratio']:.2f} | "
                    f"MaxDD: {best_stats['max_drawdown_pct']:.2f}% | "
                    f"Params: Z={best_params['entry_z']}, LB_Bars={best_params['lookback_bars']}"
                )
            else:
                logger.warning(f"  ✗ INCINERATED | Best PnL: {best_net_pnl*100:.2f}% — no viable parameter set.")

        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("  STRESS TEST COMPLETE")
        logger.info(f"  Survivors: {len(surviving_pairs)} / {len(pairs)} pairs")
        logger.info("═══════════════════════════════════════════════════════════")

        universe_dir = f"data/universes/{timeframe}"
        os.makedirs(universe_dir, exist_ok=True)
        with open(f"{universe_dir}/surviving_pairs.json", "w") as f:
            json.dump(surviving_pairs, f, indent=4)

        logger.info(f"Results written to {universe_dir}/surviving_pairs.json")
        return True
