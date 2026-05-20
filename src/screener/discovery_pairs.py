"""Cointegrated-pair discovery helpers."""

from typing import Any

import numpy as np
import pandas as pd
from statsmodels.tools.sm_exceptions import MissingDataError

from src.core.logger import logger
from src.engine.analysis.cointegration import CointegrationEngine
from src.engine.analysis.spread_math import require_positive_finite_prices
from src.engine.trader.config import StrategyConfig, UniverseConfig
from src.research.pair_baseline import apply_research_baseline_fields


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
    try:
        df_pair = _build_positive_price_pair(mature_pool[asset_x], mature_pool[asset_y])
    except ValueError as exc:
        logger.warning(f"Rejected {asset_x}/{asset_y}: invalid raw price data ({exc})")
        return None
    if len(df_pair) < 500:
        return None

    try:
        result = cointegration_engine.evaluate(df_pair.iloc[:, 0], df_pair.iloc[:, 1])
    except (MissingDataError, ValueError, np.linalg.LinAlgError) as exc:
        logger.warning(f"Rejected {asset_x}/{asset_y}: invalid cointegration data ({exc})")
        return None
    if not result["is_cointegrated"]:
        return None
    return apply_research_baseline_fields({
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
    }, df_pair)


def _build_positive_price_pair(
    asset_x: pd.DataFrame,
    asset_y: pd.DataFrame,
) -> pd.DataFrame:
    prices = pd.concat(
        [
            pd.to_numeric(asset_x["close"], errors="coerce"),
            pd.to_numeric(asset_y["close"], errors="coerce"),
        ],
        axis=1,
    )
    prices.columns = ["asset_x_close", "asset_y_close"]
    return pd.DataFrame({
        "asset_x_close": require_positive_finite_prices(prices["asset_x_close"], "asset_x"),
        "asset_y_close": require_positive_finite_prices(prices["asset_y_close"], "asset_y"),
    })
