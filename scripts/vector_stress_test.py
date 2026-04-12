"""
Epoch 2: Vectorized Stress Test Orchestrator
=============================================
Subjects all Epoch 1 cointegrated pairs to brutal operational realism:
  - Rolling Volatility Parity weighting (sizing IS the strategy)
  - Pessimistic wick-based slippage on entries
  - Continuous funding rate bleed + double taker fees
  - 2D Grid Search over Z-Score thresholds and lookback windows
"""

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

# ─── Grid Search Parameters ───────────────────────────────────────────
LOOKBACK_DAYS = [7, 14, 21]                     # Rolling window in days
ENTRY_Z_SCORES = [1.5, 2.0, 2.5]                # Z-Score entry thresholds
EXIT_Z = 0.0                                     # Mean reversion exit
BARS_PER_DAY = 6                                 # 4H candles per day
VOL_LOOKBACK_BARS = 14 * BARS_PER_DAY            # 14-day rolling vol for parity


def load_pairs() -> list:
    path = "data/universes/pairs.json"
    with open(path, "r") as f:
        return json.load(f)


def build_unified_df(symbol_a: str, symbol_b: str, storage: ParquetStorage) -> Optional[pd.DataFrame]:
    """
    Loads both assets, inner-joins on timestamp, and constructs
    the unified DataFrame required by the Vectorized Engine.
    """
    try:
        df_a = storage.load_ohlcv(symbol_a, "4h", exchange="binanceusdm")
        df_b = storage.load_ohlcv(symbol_b, "4h", exchange="binanceusdm")
    except Exception as e:
        logger.warning(f"Failed loading parquet for {symbol_a}/{symbol_b}: {e}")
        return None

    # Strict inner-join on timestamp to prevent alignment drift
    df_a = df_a.set_index("timestamp").add_prefix("A_")
    df_b = df_b.set_index("timestamp").add_prefix("B_")

    merged = df_a.join(df_b, how="inner")

    if len(merged) < 500:
        logger.warning(f"Insufficient overlap for {symbol_a}/{symbol_b}: {len(merged)} bars")
        return None

    return merged


def inject_volatility_parity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates rolling inverse-volatility weights as pure vectorized
    pandas operations. This is the mathematical core that ensures
    sizing IS the strategy.

    w_A = (1/σ_A) / (1/σ_A + 1/σ_B)
    w_B = (1/σ_B) / (1/σ_A + 1/σ_B)

    Where σ is the rolling standard deviation of log returns.
    """
    # Log returns for volatility estimation
    ret_a = np.log(df["A_close"] / df["A_close"].shift(1))
    ret_b = np.log(df["B_close"] / df["B_close"].shift(1))

    # Rolling volatility (14-day window on 4H bars)
    vol_a = ret_a.rolling(window=VOL_LOOKBACK_BARS, min_periods=VOL_LOOKBACK_BARS).std()
    vol_b = ret_b.rolling(window=VOL_LOOKBACK_BARS, min_periods=VOL_LOOKBACK_BARS).std()

    # Inverse volatility weights (vectorized parity)
    inv_a = 1.0 / vol_a
    inv_b = 1.0 / vol_b
    sum_inv = inv_a + inv_b

    df["weight_A"] = (inv_a / sum_inv).fillna(0.5)
    df["weight_B"] = (inv_b / sum_inv).fillna(0.5)

    return df


def build_zscore(df: pd.DataFrame, lookback_bars: int) -> pd.DataFrame:
    """
    Constructs the rolling spread and Z-score using log prices.
    Spread = ln(A) - hedge_ratio * ln(B)
    For the vectorized sweep, we use the simple log-price spread
    and let the Z-score normalize it.
    """
    log_a = np.log(df["A_close"])
    log_b = np.log(df["B_close"])

    spread = log_a - log_b

    rolling_mean = spread.rolling(window=lookback_bars, min_periods=lookback_bars).mean()
    rolling_std = spread.rolling(window=lookback_bars, min_periods=lookback_bars).std()

    # Prevent division by zero on flat spreads
    rolling_std = rolling_std.replace(0.0, np.nan)

    df["z_score"] = (spread - rolling_mean) / rolling_std

    return df


def run_stress_test():
    logger.info("═══════════════════════════════════════════════════════════")
    logger.info("  EPOCH 2: Vectorized Stress Test Orchestrator")
    logger.info("═══════════════════════════════════════════════════════════")

    storage = ParquetStorage()
    pairs = load_pairs()
    logger.info(f"Loaded {len(pairs)} cointegrated pairs from Epoch 1.")

    sim = Simulator()
    friction = FrictionEngine(maker_fee=0.0002, taker_fee=0.0006, annual_fund_rate=0.10)

    # Parameter grid
    grid = list(product(LOOKBACK_DAYS, ENTRY_Z_SCORES))
    logger.info(f"Grid Search: {len(grid)} parameter combinations per pair.")
    logger.info(f"Total simulations: {len(pairs) * len(grid)}")

    surviving_pairs = []

    for pair_idx, pair in enumerate(pairs):
        asset_x = pair["Asset_X"]
        asset_y = pair["Asset_Y"]
        pair_label = f"{asset_x} / {asset_y}"

        logger.info(f"[{pair_idx+1}/{len(pairs)}] Stress-testing: {pair_label}")

        unified = build_unified_df(asset_x, asset_y, storage)
        if unified is None:
            continue

        # Inject volatility parity weights ONCE per pair (shared across grid)
        unified = inject_volatility_parity(unified)

        best_net_pnl = -np.inf
        best_params = None
        best_stats = None

        for lookback_days, entry_z in grid:
            lookback_bars = lookback_days * BARS_PER_DAY

            # Clone the unified df for this parameter combo
            df = unified.copy()
            df = build_zscore(df, lookback_bars)

            # Drop NaN warm-up rows
            df = df.dropna(subset=["z_score"]).reset_index(drop=True)
            if len(df) < 200:
                continue

            # Phase 5: Vectorized Arena
            gross_df = sim.run(df, entry_z=entry_z, exit_z=EXIT_Z)

            # Apply Volatility Parity to gross returns
            # Instead of: gross_return = position * (ret_A - ret_B)
            # We compute: gross_return = position * (w_A * ret_A - w_B * ret_B)
            gross_df["gross_returns"] = gross_df["position"] * (
                gross_df["weight_A"] * gross_df["trade_ret_A"]
                - gross_df["weight_B"] * gross_df["trade_ret_B"]
            )
            gross_df["gross_returns"] = gross_df["gross_returns"].fillna(0.0)

            # Phase 6: Friction Bleed
            net_df = friction.apply(gross_df)

            # Equity Curve Metrics
            equity = net_df["net_returns"].cumsum()
            final_pnl = equity.iloc[-1] if len(equity) > 0 else -np.inf

            # Max Drawdown
            rolling_max = equity.cummax()
            drawdown = equity - rolling_max
            max_dd = drawdown.min()

            # Trade count
            trades = (net_df["position"].diff().abs() > 0).sum()

            # Sharpe Ratio (annualized from 4H bars)
            if net_df["net_returns"].std() > 0:
                sharpe = (net_df["net_returns"].mean() / net_df["net_returns"].std()) * np.sqrt(365 * 6)
            else:
                sharpe = 0.0

            if final_pnl > best_net_pnl:
                best_net_pnl = final_pnl
                best_params = {"lookback_days": lookback_days, "entry_z": entry_z}
                best_stats = {
                    "final_pnl_pct": round(final_pnl * 100, 4),
                    "max_drawdown_pct": round(max_dd * 100, 4),
                    "sharpe_ratio": round(sharpe, 4),
                    "total_trades": int(trades),
                    "bars_tested": len(net_df)
                }

        # Incinerator Logic: Only surviving pairs with positive best-case PnL
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
                f"Params: Z={best_params['entry_z']}, LB={best_params['lookback_days']}d"
            )
        else:
            logger.warning(f"  ✗ INCINERATED | Best PnL: {best_net_pnl*100:.2f}% — no viable parameter set.")

    # ─── Export ────────────────────────────────────────────────────────
    logger.info("═══════════════════════════════════════════════════════════")
    logger.info("  STRESS TEST COMPLETE")
    logger.info(f"  Survivors: {len(surviving_pairs)} / {len(pairs)} pairs")
    logger.info("═══════════════════════════════════════════════════════════")

    os.makedirs("data/universes", exist_ok=True)
    with open("data/universes/surviving_pairs.json", "w") as f:
        json.dump(surviving_pairs, f, indent=4)

    logger.info("Results written to data/universes/surviving_pairs.json")


if __name__ == "__main__":
    run_stress_test()
