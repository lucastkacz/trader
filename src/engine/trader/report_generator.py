"""
Trader Report CLI
=================
Comprehensive reporting interface for the trading system.
"""

import argparse
import json

from src.core.logger import configure_logger
from src.engine.trader.report_engine import TradeReport, generate_report
from src.engine.trader.reporting.export import export_json, export_markdown
from src.engine.trader.reporting.render_terminal import (
    render_backtest_comparison,
    render_executive_summary,
    render_per_pair,
    render_pair_validity,
    render_portfolio_metrics,
    render_risk,
    render_signal_quality,
    render_state_ledger,
    render_trade_log,
)
from src.engine.trader.runtime.pair_validity.models import PairValidityConfig
from src.engine.trader.state_manager import TradeStateManager

__all__ = [
    "TradeReport",
    "export_json",
    "export_markdown",
    "main",
    "render_backtest_comparison",
    "render_executive_summary",
    "render_per_pair",
    "render_pair_validity",
    "render_portfolio_metrics",
    "render_risk",
    "render_signal_quality",
    "render_state_ledger",
    "render_trade_log",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper Trader Report")
    parser.add_argument("--db-path", type=str, required=True, help="Path to the SQLite database (e.g. data/dev/trades_1m.db)")
    parser.add_argument("--min-sharpe", type=float, required=True, help="Minimum Sharpe ratio for Tier 1 filtering")
    parser.add_argument(
        "--surviving-pairs-path",
        type=str,
        required=True,
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

    if args.json:
        configure_logger(log_level="silent")

    state = TradeStateManager(db_path=args.db_path)

    try:
        report = generate_report(
            state,
            min_sharpe=args.min_sharpe,
            surviving_pairs_path=args.surviving_pairs_path,
            market_data_base_dir=args.market_data_base_dir,
            pair_validity_config=_pair_validity_config(args),
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
    if args.market_data_base_dir is None:
        return None
    return PairValidityConfig(
        recent_window_bars=args.pair_validity_window_bars,
        min_recent_bars=args.pair_validity_min_bars,
        open_position_review_half_life_multiple=(
            args.open_position_review_half_life_multiple
        ),
    )


if __name__ == "__main__":
    main()
