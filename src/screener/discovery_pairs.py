"""Cointegrated-pair discovery helpers."""

from typing import Any

import numpy as np
import pandas as pd

from src.core.logger import logger
from src.engine.analysis.cointegration import CointegrationEngine
from src.engine.trader.config import StrategyConfig, UniverseConfig


def discover_cointegrated_pairs(
    mature_pool: dict[str, pd.DataFrame],
    clusters: dict[str, list[str]],
    universe_cfg: UniverseConfig,
    strategy_cfg: StrategyConfig,
) -> list[dict[str, Any]]:
    coint_cfg = universe_cfg.cointegration
    cointegration_engine = CointegrationEngine(
        p_value_threshold=coint_cfg.p_value_threshold,
        max_half_life_bars=coint_cfg.max_half_life_bars,
        ewma_span_bars=coint_cfg.ewma_span_bars,
    )

    final_pairs = []
    for cohort_name, members in clusters.items():
        logger.debug(f"Evaluating {cohort_name} ({len(members)} assets)...")
        final_pairs.extend(
            _discover_cluster_pairs(
                cohort_name,
                members,
                mature_pool,
                cointegration_engine,
                strategy_cfg,
            )
        )
    logger.info(f"Phase 4 Alpha Core yielded {len(final_pairs)} pristine pairs.")
    return final_pairs


def _discover_cluster_pairs(
    cohort_name: str,
    members: list[str],
    mature_pool: dict[str, pd.DataFrame],
    cointegration_engine: CointegrationEngine,
    strategy_cfg: StrategyConfig,
) -> list[dict[str, Any]]:
    final_pairs = []
    for left_index in range(len(members)):
        for right_index in range(left_index + 1, len(members)):
            pair = _evaluate_member_pair(
                cohort_name,
                members[left_index],
                members[right_index],
                mature_pool,
                cointegration_engine,
                strategy_cfg,
            )
            if pair is not None:
                final_pairs.append(pair)
    return final_pairs


def _evaluate_member_pair(
    cohort_name: str,
    asset_x: str,
    asset_y: str,
    mature_pool: dict[str, pd.DataFrame],
    cointegration_engine: CointegrationEngine,
    strategy_cfg: StrategyConfig,
) -> dict[str, Any] | None:
    series_x = np.log(mature_pool[asset_x]["close"])
    series_y = np.log(mature_pool[asset_y]["close"])
    df_pair = pd.concat([series_x, series_y], axis=1).dropna()
    if len(df_pair) < 500:
        return None

    result = cointegration_engine.evaluate(df_pair.iloc[:, 0], df_pair.iloc[:, 1])
    if not result["is_cointegrated"]:
        return None
    return {
        "Cohort": cohort_name,
        "Asset_X": asset_x,
        "Asset_Y": asset_y,
        "P_Value": result["p_value"],
        "Hedge_Ratio": result["hedge_ratio"],
        "Half_Life": result["half_life"],
        "Best_Params": {
            "lookback_bars": strategy_cfg.execution.ew_ols_lookback_bars,
            "entry_z": strategy_cfg.execution.entry_z_score,
        },
        "Performance": {
            "sharpe_ratio": 1.0,
            "final_pnl_pct": 0.0,
        },
    }
