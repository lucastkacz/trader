"""
Trader Report CLI
=================
Comprehensive reporting interface for the trading system.
"""

import argparse
import json

from src.core.logger import configure_logger
from src.engine.trader.config import load_pipeline_config
from src.engine.trader.reporting.assembler import generate_report
from src.engine.trader.reporting.export import export_json, export_markdown
from src.engine.trader.reporting.models import TradeReport
from src.engine.trader.reporting.render_terminal import (
    render_backtest_comparison,
    render_executive_summary,
    render_per_pair,
    render_pair_validity,
    render_pair_queue,
    render_portfolio_metrics,
    render_risk,
    render_signal_quality,
    render_state_ledger,
    render_trade_log,
)
from src.engine.trader.runtime.pair_validity.models import PairValidityConfig
from src.engine.trader.runtime.pair_queue import PairQueuePolicy
from src.engine.trader.runtime.pairs import promoted_pair_artifact_path
from src.engine.trader.state.manager import TradeStateManager

__all__ = [
    "TradeReport",
    "export_json",
    "export_markdown",
    "main",
    "render_backtest_comparison",
    "render_executive_summary",
    "render_per_pair",
    "render_pair_validity",
    "render_pair_queue",
    "render_portfolio_metrics",
    "render_risk",
    "render_signal_quality",
    "render_state_ledger",
    "render_trade_log",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper Trader Report")
    parser.add_argument(
        "--pipeline",
        type=str,
        default=None,
        help="Optional typed pipeline YAML used to derive report paths and queue policy",
    )
    parser.add_argument("--db-path", type=str, default=None, help="Path to the SQLite database (e.g. data/dev/trades_1m.db)")
    parser.add_argument("--min-sharpe", type=float, default=None, help="Minimum Sharpe ratio for Tier 1 filtering")
    parser.add_argument(
        "--surviving-pairs-path",
        type=str,
        default=None,
        help="Path to the surviving_pairs.json artifact used for backtest comparison",
    )
    parser.add_argument("--detailed", action="store_true", help="Show full trade log and signal quality")
    parser.add_argument("--pair", type=str, default=None, help='Single pair deep-dive (e.g. "MET/USDT|LTC/USDT")')
    parser.add_argument("--json", action="store_true", help="Output full report as JSON to stdout")
    parser.add_argument("--export", action="store_true", help="Save JSON + Markdown reports to data/reports/")
    parser.add_argument(
        "--market-data-base-dir",
        type=str,
        default=None,
        help="Optional parquet base directory for read-only pair validity diagnostics",
    )
    parser.add_argument(
        "--pair-validity-window-bars",
        type=int,
        default=None,
        help="Recent closed-bar window for pair validity diagnostics",
    )
    parser.add_argument(
        "--pair-validity-min-bars",
        type=int,
        default=30,
        help="Minimum recent bars required before drift diagnostics are trusted",
    )
    parser.add_argument(
        "--open-position-review-half-life-multiple",
        type=float,
        default=None,
        help="Flag open positions held beyond this research half-life multiple",
    )
    args = parser.parse_args()
    report_inputs = _resolve_report_inputs(args)

    if args.json:
        configure_logger(log_level="silent")

    state = TradeStateManager(db_path=report_inputs["db_path"])

    try:
        report = generate_report(
            state,
            min_sharpe=report_inputs["min_sharpe"],
            surviving_pairs_path=report_inputs["surviving_pairs_path"],
            market_data_base_dir=report_inputs["market_data_base_dir"],
            pair_validity_config=_pair_validity_config(args),
            pair_queue_policy=report_inputs["pair_queue_policy"],
            pair_queue_enabled=report_inputs["pair_queue_enabled"],
        )

        if args.json:
            print(json.dumps(report.to_dict(), indent=2, default=str))
            return

        if args.export:
            json_path = export_json(report)
            md_path = export_markdown(report)
            print(f"Exported JSON:     {json_path}")
            print(f"Exported Markdown: {md_path}")
            render_executive_summary(report)
            return

        render_executive_summary(report)
        render_portfolio_metrics(report)
        render_per_pair(report, filter_pair=args.pair)
        if report.pair_validity is not None:
            render_pair_validity(report, filter_pair=args.pair)
        if report.pair_queue is not None:
            render_pair_queue(report, filter_pair=args.pair)

        if args.detailed or args.pair:
            render_trade_log(report, filter_pair=args.pair)
            render_signal_quality(report)

        render_state_ledger(report)
        render_risk(report)
        render_backtest_comparison(report)
        print()

    finally:
        state.close()


def _pair_validity_config(args: argparse.Namespace) -> PairValidityConfig | None:
    if args.market_data_base_dir is None and args.pipeline is None:
        return None
    return PairValidityConfig(
        recent_window_bars=args.pair_validity_window_bars,
        min_recent_bars=args.pair_validity_min_bars,
        open_position_review_half_life_multiple=(
            args.open_position_review_half_life_multiple
        ),
    )


def _resolve_report_inputs(args: argparse.Namespace) -> dict[str, object]:
    pipeline_cfg = load_pipeline_config(args.pipeline) if args.pipeline else None
    db_path = args.db_path
    min_sharpe = args.min_sharpe
    surviving_pairs_path = args.surviving_pairs_path
    market_data_base_dir = args.market_data_base_dir
    pair_queue_enabled = True
    pair_queue_policy = None

    if pipeline_cfg is not None:
        execution_cfg = pipeline_cfg.execution
        db_path = db_path or execution_cfg.db_path
        min_sharpe = min_sharpe if min_sharpe is not None else execution_cfg.min_sharpe
        surviving_pairs_path = surviving_pairs_path or str(
            promoted_pair_artifact_path(
                pipeline_cfg.timeframe,
                execution_cfg.artifact_base_dir,
            )
        )
        market_data_base_dir = market_data_base_dir or execution_cfg.market_data_base_dir
        pair_queue_enabled = execution_cfg.pair_queue.enabled
        pair_queue_policy = PairQueuePolicy(
            **execution_cfg.pair_queue.to_runtime_policy_kwargs()
        )

    missing = [
        name
        for name, value in (
            ("--db-path", db_path),
            ("--min-sharpe", min_sharpe),
            ("--surviving-pairs-path", surviving_pairs_path),
        )
        if value is None
    ]
    if missing:
        missing_text = ", ".join(missing)
        raise SystemExit(
            f"Either pass --pipeline or provide required report inputs: {missing_text}"
        )

    return {
        "db_path": db_path,
        "min_sharpe": min_sharpe,
        "surviving_pairs_path": surviving_pairs_path,
        "market_data_base_dir": market_data_base_dir,
        "pair_queue_enabled": pair_queue_enabled,
        "pair_queue_policy": pair_queue_policy,
    }


if __name__ == "__main__":
    main()
