"""
Trader Report CLI
=================
Comprehensive reporting interface for the trading system.
"""

import argparse
import json

from src.engine.trader.report_engine import TradeReport, generate_report
from src.engine.trader.reporting.export import export_json, export_markdown
from src.engine.trader.reporting.render_terminal import (
    render_backtest_comparison,
    render_executive_summary,
    render_per_pair,
    render_portfolio_metrics,
    render_risk,
    render_signal_quality,
    render_state_ledger,
    render_trade_log,
)
from src.engine.trader.state_manager import TradeStateManager

__all__ = [
    "TradeReport",
    "export_json",
    "export_markdown",
    "main",
    "render_backtest_comparison",
    "render_executive_summary",
    "render_per_pair",
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
    parser.add_argument("--detailed", action="store_true", help="Show full trade log and signal quality")
    parser.add_argument("--pair", type=str, default=None, help='Single pair deep-dive (e.g. "MET/USDT|LTC/USDT")')
    parser.add_argument("--json", action="store_true", help="Output full report as JSON to stdout")
    parser.add_argument("--export", action="store_true", help="Save JSON + Markdown reports to data/reports/")
    args = parser.parse_args()

    state = TradeStateManager(db_path=args.db_path)

    try:
        report = generate_report(state, min_sharpe=args.min_sharpe)

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

        if args.detailed or args.pair:
            render_trade_log(report, filter_pair=args.pair)
            render_signal_quality(report)

        render_state_ledger(report)
        render_risk(report)
        render_backtest_comparison(report)
        print()

    finally:
        state.close()


if __name__ == "__main__":
    main()
