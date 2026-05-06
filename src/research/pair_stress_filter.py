"""Research workflow for stress-filtering candidate statistical-arbitrage pairs."""

from itertools import product
from pathlib import Path
from typing import Any

from src.core.logger import logger
from src.data.storage.local_parquet import ParquetStorage
from src.engine.trader.config import BacktestConfig, StrategyConfig
from src.engine.trader.runtime.pairs import write_candidate_pair_artifact
from src.research.pair_stress_data import build_unified_ohlcv, load_candidate_pairs
from src.research.pair_stress_simulation import (
    build_performance_stats,
    inject_volatility_parity,
    simulate_parameter_set,
)
from src.simulation.friction_model import FrictionEngine
from src.simulation.vectorized_engine import Simulator
from src.utils.timeframe_math import get_bars_per_year


class PairStressFilter:
    """Run offline stress filtering over candidate pairs and write a new candidate artifact."""

    def __init__(self, storage: ParquetStorage):
        self.storage = storage

    def run(
        self,
        timeframe: str,
        exchange: str,
        input_pairs_path: str | Path,
        output_artifact_base_dir: str | Path,
        backtest_cfg: BacktestConfig,
        strategy_cfg: StrategyConfig,
    ) -> Path:
        logger.info("Starting pair stress filter research workflow")
        pairs = load_candidate_pairs(input_pairs_path, timeframe, exchange)
        logger.info(f"Loaded {len(pairs)} candidate pairs for stress filtering.")

        grid = list(product(
            backtest_cfg.grid_search.lookback_bars,
            backtest_cfg.grid_search.entry_z_scores,
        ))
        logger.info(f"Grid search combinations per pair: {len(grid)}")

        simulator = Simulator()
        friction = FrictionEngine(
            maker_fee=backtest_cfg.friction.maker_fee,
            taker_fee=backtest_cfg.friction.taker_fee,
            annual_fund_rate=backtest_cfg.friction.annual_fund_rate,
        )
        bars_per_year = get_bars_per_year(timeframe)
        surviving_pairs = []

        for pair_index, pair in enumerate(pairs):
            survivor = self._stress_filter_one_pair(
                pair=pair,
                pair_index=pair_index,
                pair_count=len(pairs),
                timeframe=timeframe,
                exchange=exchange,
                grid=grid,
                simulator=simulator,
                friction=friction,
                bars_per_year=bars_per_year,
                strategy_cfg=strategy_cfg,
            )
            if survivor is not None:
                surviving_pairs.append(survivor)

        candidate_path = write_candidate_pair_artifact(
            pair_rows=surviving_pairs,
            timeframe=timeframe,
            exchange=exchange,
            base_dir=output_artifact_base_dir,
        )
        logger.info(f"Pair stress filter wrote candidate artifact: {candidate_path}")
        return candidate_path

    def _stress_filter_one_pair(
        self,
        pair: dict[str, Any],
        pair_index: int,
        pair_count: int,
        timeframe: str,
        exchange: str,
        grid: list[tuple[int, float]],
        simulator: Simulator,
        friction: FrictionEngine,
        bars_per_year: int,
        strategy_cfg: StrategyConfig,
    ) -> dict[str, Any] | None:
        asset_x = pair["Asset_X"]
        asset_y = pair["Asset_Y"]
        hedge_ratio = pair["Hedge_Ratio"]
        logger.info(f"[{pair_index + 1}/{pair_count}] Stress filtering: {asset_x} / {asset_y}")

        unified = build_unified_ohlcv(self.storage, asset_x, asset_y, timeframe, exchange)
        if unified is None:
            return None
        unified = inject_volatility_parity(
            unified,
            strategy_cfg.execution.volatility_lookback_bars,
        )

        best_params, best_stats, best_net_pnl = find_best_parameters(
            unified=unified,
            hedge_ratio=hedge_ratio,
            grid=grid,
            simulator=simulator,
            friction=friction,
            bars_per_year=bars_per_year,
            exit_z=strategy_cfg.execution.exit_z_score,
        )
        if best_net_pnl <= 0 or best_params is None or best_stats is None:
            logger.warning(f"Rejected pair {asset_x} / {asset_y}: best pnl={best_net_pnl * 100:.2f}%")
            return None

        logger.info(
            f"Survived {asset_x} / {asset_y}: "
            f"pnl={best_stats['final_pnl_pct']:.2f}% sharpe={best_stats['sharpe_ratio']:.2f}"
        )
        return {
            "Cohort": pair["Cohort"],
            "Asset_X": asset_x,
            "Asset_Y": asset_y,
            "Hedge_Ratio": pair["Hedge_Ratio"],
            "Half_Life": pair["Half_Life"],
            "P_Value": pair["P_Value"],
            "Best_Params": best_params,
            "Performance": best_stats,
        }


def find_best_parameters(
    unified: Any,
    hedge_ratio: float,
    grid: list[tuple[int, float]],
    simulator: Simulator,
    friction: FrictionEngine,
    bars_per_year: int,
    exit_z: float,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, float]:
    best_net_pnl = float("-inf")
    best_params = None
    best_stats = None
    for lookback_bars, entry_z in grid:
        net_df = simulate_parameter_set(
            unified=unified,
            hedge_ratio=hedge_ratio,
            lookback_bars=lookback_bars,
            entry_z=entry_z,
            exit_z=exit_z,
            simulator=simulator,
            friction=friction,
        )
        if net_df is None:
            continue

        final_pnl = net_df["net_returns"].sum()
        if final_pnl > best_net_pnl:
            best_net_pnl = final_pnl
            best_params = {"lookback_bars": lookback_bars, "entry_z": entry_z}
            best_stats = build_performance_stats(net_df, bars_per_year)
    return best_params, best_stats, best_net_pnl
