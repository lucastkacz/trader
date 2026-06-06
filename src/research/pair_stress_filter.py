"""Research workflow for stress-filtering candidate statistical-arbitrage pairs."""

from itertools import product
from pathlib import Path
from typing import Any

from src.core.logger import logger
from src.data.storage.local_parquet import LocalOHLCVParquetStore
from src.engine.trader.config import BacktestConfig, StrategyConfig
from src.engine.trader.runtime.artifacts import write_candidate_pair_artifact
from src.research.pair_stress_data import build_unified_ohlcv, load_candidate_pairs
from src.research.pair_baseline import (
    apply_research_baseline_fields,
    prices_from_unified_ohlcv,
)
from src.research.pair_stress_report import (
    build_rejected_pair_report,
    build_surviving_pair_report,
    extract_source_window,
    write_pair_stress_report,
)
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

    def __init__(self, storage: LocalOHLCVParquetStore):
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
        report_rows = []

        for pair_index, pair in enumerate(pairs):
            survivor, report_row = self._stress_filter_one_pair(
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
            report_rows.append(report_row)

        candidate_path = write_candidate_pair_artifact(
            pair_rows=surviving_pairs,
            timeframe=timeframe,
            exchange=exchange,
            base_dir=output_artifact_base_dir,
        )
        report_path = write_pair_stress_report(
            report_rows=report_rows,
            timeframe=timeframe,
            exchange=exchange,
            base_dir=output_artifact_base_dir,
        )
        logger.info(f"Pair stress filter wrote candidate artifact: {candidate_path}")
        logger.info(f"Pair stress filter wrote trace report: {report_path}")
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
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        asset_x = pair["Asset_X"]
        asset_y = pair["Asset_Y"]
        hedge_ratio = pair["Hedge_Ratio"]
        logger.info(f"[{pair_index + 1}/{pair_count}] Stress filtering: {asset_x} / {asset_y}")

        unified = build_unified_ohlcv(self.storage, asset_x, asset_y, timeframe, exchange)
        if unified is None:
            return None, build_rejected_pair_report(pair, "source_data_unavailable")
        source_window = extract_source_window(unified)
        unified = inject_volatility_parity(
            unified,
            strategy_cfg.execution.volatility_lookback_bars,
        )

        try:
            best_params, best_stats, best_net_pnl, best_net_df = find_best_parameters(
                unified=unified,
                hedge_ratio=hedge_ratio,
                grid=grid,
                simulator=simulator,
                friction=friction,
                bars_per_year=bars_per_year,
                exit_z=strategy_cfg.execution.exit_z_score,
            )
        except ValueError as exc:
            logger.warning(f"Rejected pair {asset_x} / {asset_y}: invalid stress data ({exc})")
            return None, build_rejected_pair_report(pair, f"invalid_stress_data: {exc}", source_window)
        if best_net_pnl <= 0 or best_params is None or best_stats is None:
            logger.warning(f"Rejected pair {asset_x} / {asset_y}: best pnl={best_net_pnl * 100:.2f}%")
            return None, build_rejected_pair_report(pair, f"non_positive_best_pnl: {best_net_pnl:.8f}", source_window)

        logger.info(
            f"Survived {asset_x} / {asset_y}: "
            f"pnl={best_stats['final_pnl_pct']:.2f}% sharpe={best_stats['sharpe_ratio']:.2f}"
        )
        survivor = apply_research_baseline_fields({
            "Cohort": pair["Cohort"],
            "Asset_X": asset_x,
            "Asset_Y": asset_y,
            "Hedge_Ratio": pair["Hedge_Ratio"],
            "Half_Life": pair["Half_Life"],
            "P_Value": pair["P_Value"],
            "Best_Params": best_params,
            "Performance": best_stats,
        }, prices_from_unified_ohlcv(unified), lookback_bars=best_params["lookback_bars"])
        report_row = build_surviving_pair_report(
            pair=pair,
            source_window=source_window,
            stress_params={
                "lookback_bars": best_params["lookback_bars"],
                "entry_z": best_params["entry_z"],
                "exit_z": strategy_cfg.execution.exit_z_score,
            },
            net_df=best_net_df,
        )
        return survivor, report_row


def find_best_parameters(
    unified: Any,
    hedge_ratio: float,
    grid: list[tuple[int, float]],
    simulator: Simulator,
    friction: FrictionEngine,
    bars_per_year: int,
    exit_z: float,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, float, Any]:
    best_net_pnl = float("-inf")
    best_params = None
    best_stats = None
    best_net_df = None
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
            best_net_df = net_df
    return best_params, best_stats, best_net_pnl, best_net_df
