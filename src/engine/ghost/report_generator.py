"""
Epoch 3: Paper Trader Report CLI
==================================
Comprehensive reporting interface for the paper trading system.
Calls report_engine.py for computation → renders to terminal, JSON, or Markdown.

Usage:
    PYTHONPATH=. python -m src.engine.ghost.report_generator --db-path data/dev/trades_1m.db --min-sharpe 1.0
    PYTHONPATH=. python -m src.engine.ghost.report_generator --db-path data/uat/trades_4h.db --min-sharpe 1.0 --detailed
    PYTHONPATH=. python -m src.engine.ghost.report_generator --db-path data/dev/trades_1m.db --min-sharpe 1.0 --pair "MET/USDT|LTC/USDT"
    PYTHONPATH=. python -m src.engine.ghost.report_generator --db-path data/dev/trades_1m.db --min-sharpe 1.0 --json
    PYTHONPATH=. python -m src.engine.ghost.report_generator --db-path data/dev/trades_1m.db --min-sharpe 1.0 --export
"""

import os
import json
import argparse
from datetime import datetime, timezone

from src.engine.ghost.state_manager import GhostStateManager
from src.engine.ghost.report_engine import generate_report, GhostReport


# ─── Terminal Colors (ANSI) ──────────────────────────────────────

class C:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"


def _status_color(status: str) -> str:
    if status == "HEALTHY":
        return f"{C.GREEN}🟢 HEALTHY{C.RESET}"
    elif status == "DEGRADED":
        return f"{C.YELLOW}🟡 DEGRADED{C.RESET}"
    else:
        return f"{C.RED}🔴 FAILING{C.RESET}"


def _pnl_color(pnl: float) -> str:
    if pnl > 0:
        return f"{C.GREEN}{pnl*100:+.4f}%{C.RESET}"
    elif pnl < 0:
        return f"{C.RED}{pnl*100:+.4f}%{C.RESET}"
    else:
        return f"{C.DIM}{pnl*100:+.4f}%{C.RESET}"


def _metric(label: str, value: str, width: int = 32) -> str:
    return f"  {C.DIM}{label + ':':<{width}}{C.RESET} {C.BOLD}{value}{C.RESET}"


def _header(title: str):
    line = "═" * 62
    print(f"\n{C.CYAN}{line}{C.RESET}")
    print(f"  {C.BOLD}{C.WHITE}{title}{C.RESET}")
    print(f"{C.CYAN}{line}{C.RESET}")


def _subheader(title: str):
    print(f"\n  {C.BLUE}── {title} ──{C.RESET}")


# ─── Renderers ───────────────────────────────────────────────────

def render_executive_summary(report: GhostReport):
    _header("EXECUTIVE SUMMARY")
    print(_metric("Status", _status_color(report.status)))
    print(_metric("Total Equity", _pnl_color(report.total_equity_pct)))
    print(_metric("Realized PnL", _pnl_color(report.realized_pnl_pct)))
    print(_metric("Unrealized PnL", _pnl_color(report.unrealized_pnl_pct)))
    print(_metric("Active Pairs", str(report.active_pairs)))
    print(_metric("Total Trades", str(report.total_trades)))
    print(_metric("Uptime", f"{report.uptime_hours:.1f}h"))
    print(_metric("Bar Interval", f"{24*365/report.bars_per_year:.1f}h ({report.bars_per_year:.0f}/yr)"))


def render_portfolio_metrics(report: GhostReport):
    _header("PORTFOLIO METRICS")

    def _fmt_opt(val, fmt=".4f"):
        return f"{val:{fmt}}" if val is not None else "N/A"

    print(_metric("Sharpe Ratio (ann.)", _fmt_opt(report.sharpe_ratio, ".4f")))
    print(_metric("Sortino Ratio (ann.)", _fmt_opt(report.sortino_ratio, ".4f")))
    print(_metric("Max Drawdown", f"{report.max_drawdown_pct*100:.4f}%"))
    print(_metric("Calmar Ratio", _fmt_opt(report.calmar_ratio, ".4f")))
    print(_metric("Win Rate", f"{report.win_rate*100:.1f}%"))
    print(_metric("Profit Factor", _fmt_opt(report.profit_factor, ".4f")))
    print(_metric("Expectancy", f"{report.expectancy*100:.4f}%"))
    print(_metric("Avg Holding Period", f"{report.avg_holding_bars:.1f} bars"))
    print(_metric("Trades / Week", f"{report.trades_per_week:.2f}"))


def render_per_pair(report: GhostReport, filter_pair: str = None):
    _header("PER-PAIR BREAKDOWN")

    pairs = report.per_pair
    if filter_pair:
        pairs = [p for p in pairs if p.pair_label == filter_pair]
        if not pairs:
            print(f"  {C.RED}No data found for pair: {filter_pair}{C.RESET}")
            return

    # Table header
    print(f"  {C.DIM}{'Pair':<30} {'Status':<14} {'Trades':>6} {'Win%':>6} "
          f"{'Realized':>10} {'Avg PnL':>10} {'BT Sharpe':>10} {'Match':>12}{C.RESET}")
    print(f"  {C.DIM}{'─'*30} {'─'*14} {'─'*6} {'─'*6} {'─'*10} {'─'*10} {'─'*10} {'─'*12}{C.RESET}")

    for p in pairs:
        status_icon = "●" if p.current_status != "FLAT" else "○"
        status_str = f"{status_icon} {p.current_status}"

        bt_sharpe_str = f"{p.backtest_sharpe:.2f}" if p.backtest_sharpe is not None else "N/A"
        match_color = C.GREEN if p.live_vs_backtest == "ALIGNED" else (
            C.RED if p.live_vs_backtest == "DIVERGING" else C.DIM
        )

        print(
            f"  {p.pair_label:<30} {status_str:<14} {p.trade_count:>6} "
            f"{p.win_rate*100:>5.1f}% {p.realized_pnl*100:>+9.4f}% "
            f"{p.avg_pnl_per_trade*100:>+9.4f}% {bt_sharpe_str:>10} "
            f"{match_color}{p.live_vs_backtest:>12}{C.RESET}"
        )

        if p.current_z_score is not None:
            print(f"  {C.DIM}  └─ Z-Score: {p.current_z_score:.4f}{C.RESET}")


def render_trade_log(report: GhostReport, filter_pair: str = None):
    _header("TRADE LOG")

    trades = report.trade_log
    if filter_pair:
        trades = [t for t in trades if t.get("pair_label") == filter_pair]

    if not trades:
        print(f"  {C.DIM}No completed trades yet.{C.RESET}")
        return

    print(f"  {C.DIM}{'ID':>4} {'Pair':<28} {'Side':<14} {'Entry Z':>8} "
          f"{'PnL%':>9} {'Bars':>5} {'Result':>6}{C.RESET}")
    print(f"  {C.DIM}{'─'*4} {'─'*28} {'─'*14} {'─'*8} {'─'*9} {'─'*5} {'─'*6}{C.RESET}")

    for t in trades:
        pnl = t.get("pnl_pct") or 0.0
        marker = f"{C.GREEN}✓{C.RESET}" if pnl > 0 else f"{C.RED}✗{C.RESET}"
        bars = t.get("holding_bars") or "?"
        pnl_str = _pnl_color(pnl)
        entry_z = t.get("entry_z") or 0.0

        print(
            f"  {t.get('id', '?'):>4} {t.get('pair_label', '?'):<28} "
            f"{t.get('side', '?'):<14} {entry_z:>+8.4f} "
            f"{pnl_str:>20} {str(bars):>5} {marker:>6}"
        )


def render_signal_quality(report: GhostReport):
    _header("SIGNAL QUALITY")
    sq = report.signal_quality
    print(_metric("Signal Accuracy", f"{sq.signal_accuracy*100:.1f}%"))
    print(_metric("Avg Entry |Z|", f"{sq.avg_entry_z:.4f}"))
    exit_z_str = f"{sq.avg_exit_z:.4f}" if sq.avg_exit_z is not None else "N/A"
    print(_metric("Avg Exit |Z|", exit_z_str))
    print(_metric("False Signal Rate", f"{sq.false_signal_rate*100:.1f}%"))
    print(_metric("Total Signals Recorded", str(sq.total_signals_recorded)))


def render_risk(report: GhostReport):
    _header("RISK DASHBOARD")
    r = report.risk
    print(_metric("Portfolio Heat", f"{r.portfolio_heat*100:.4f}%"))
    print(_metric("Largest Unrealized Loss", _pnl_color(r.largest_single_loss)))
    print(_metric("Days Since Last Trade", f"{r.days_since_last_trade:.1f}"))
    print(_metric("Consecutive Losses", str(r.consecutive_losses)))
    print(_metric("Data Freshness", r.data_freshness[:19] if len(r.data_freshness) > 10 else r.data_freshness))


def render_backtest_comparison(report: GhostReport):
    _header("BACKTEST vs LIVE COMPARISON")

    bt_sharpe = f"{report.backtest_avg_sharpe:.4f}" if report.backtest_avg_sharpe else "N/A"
    bt_pnl = f"{report.backtest_avg_pnl:.2f}%" if report.backtest_avg_pnl else "N/A"
    live_sharpe = f"{report.sharpe_ratio:.4f}" if report.sharpe_ratio else "N/A"
    live_pnl = f"{report.realized_pnl_pct*100:.4f}%"

    print(f"  {C.DIM}{'Metric':<30} {'Backtest (4yr)':>15} {'Live':>15}{C.RESET}")
    print(f"  {C.DIM}{'─'*30} {'─'*15} {'─'*15}{C.RESET}")
    print(f"  {'Avg Sharpe Ratio':<30} {bt_sharpe:>15} {live_sharpe:>15}")
    print(f"  {'Avg PnL':<30} {bt_pnl:>15} {live_pnl:>15}")
    print(f"  {'Max Drawdown':<30} {'N/A':>15} {report.max_drawdown_pct*100:>+14.4f}%")

    # Sharpe health check
    if report.sharpe_ratio is not None and report.backtest_avg_sharpe is not None and report.backtest_avg_sharpe > 0:
        ratio = report.sharpe_ratio / report.backtest_avg_sharpe
        if ratio >= 0.5:
            verdict = f"{C.GREEN}VALIDATED (Live/BT = {ratio:.2f}){C.RESET}"
        elif ratio >= 0.3:
            verdict = f"{C.YELLOW}INVESTIGATE (Live/BT = {ratio:.2f}){C.RESET}"
        else:
            verdict = f"{C.RED}BROKEN (Live/BT = {ratio:.2f}){C.RESET}"
        print(f"\n  {C.BOLD}Verdict:{C.RESET} {verdict}")


# ─── Export Functions ────────────────────────────────────────────

def export_json(report: GhostReport) -> str:
    """Export report as JSON file. Returns the file path."""
    os.makedirs("data/ghost/reports", exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    path = f"data/ghost/reports/report_{ts}.json"
    with open(path, "w") as f:
        json.dump(report.to_dict(), f, indent=2, default=str)
    return path


def export_markdown(report: GhostReport) -> str:
    """Export report as Markdown file. Returns the file path."""
    os.makedirs("data/ghost/reports", exist_ok=True)

    # Determine week number from first snapshot
    week_num = 1
    if report.uptime_hours > 0:
        week_num = max(1, int(report.uptime_hours / (24 * 7)) + 1)
    path = f"data/ghost/reports/weekly_report_week{week_num:02d}.md"

    lines = []
    lines.append(f"# Paper Trader Report — Week {week_num}")
    lines.append(f"*Generated: {report.report_timestamp[:19]} UTC*\n")

    # Executive Summary
    lines.append("## Executive Summary\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Status | {report.status} |")
    lines.append(f"| Total Equity | {report.total_equity_pct*100:+.4f}% |")
    lines.append(f"| Realized PnL | {report.realized_pnl_pct*100:+.4f}% |")
    lines.append(f"| Unrealized PnL | {report.unrealized_pnl_pct*100:+.4f}% |")
    lines.append(f"| Active Pairs | {report.active_pairs} |")
    lines.append(f"| Total Trades | {report.total_trades} |")
    lines.append(f"| Uptime | {report.uptime_hours:.1f}h |")
    lines.append("")

    # Portfolio Metrics
    lines.append("## Portfolio Metrics\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")

    def _fmt(v, fmt=".4f"):
        return f"{v:{fmt}}" if v is not None else "N/A"

    lines.append(f"| Sharpe Ratio | {_fmt(report.sharpe_ratio)} |")
    lines.append(f"| Sortino Ratio | {_fmt(report.sortino_ratio)} |")
    lines.append(f"| Max Drawdown | {report.max_drawdown_pct*100:.4f}% |")
    lines.append(f"| Calmar Ratio | {_fmt(report.calmar_ratio)} |")
    lines.append(f"| Win Rate | {report.win_rate*100:.1f}% |")
    lines.append(f"| Profit Factor | {_fmt(report.profit_factor)} |")
    lines.append(f"| Expectancy | {report.expectancy*100:.4f}% |")
    lines.append(f"| Avg Holding | {report.avg_holding_bars:.1f} bars |")
    lines.append(f"| Trades/Week | {report.trades_per_week:.2f} |")
    lines.append("")

    # Per-pair
    lines.append("## Per-Pair Breakdown\n")
    lines.append("| Pair | Trades | Win% | Realized | BT Sharpe | Match |")
    lines.append("|------|--------|------|----------|-----------|-------|")
    for p in report.per_pair:
        bt_s = f"{p.backtest_sharpe:.2f}" if p.backtest_sharpe is not None else "N/A"
        lines.append(
            f"| {p.pair_label} | {p.trade_count} | {p.win_rate*100:.1f}% | "
            f"{p.realized_pnl*100:+.4f}% | {bt_s} | {p.live_vs_backtest} |"
        )
    lines.append("")

    # Trade Log
    if report.trade_log:
        lines.append("## Trade Log\n")
        lines.append("| ID | Pair | Side | Entry Z | PnL% | Bars |")
        lines.append("|----|------|------|---------|------|------|")
        for t in report.trade_log:
            pnl = t.get("pnl_pct") or 0.0
            bars = t.get("holding_bars") or "?"
            lines.append(
                f"| {t.get('id', '?')} | {t.get('pair_label', '?')} | "
                f"{t.get('side', '?')} | {t.get('entry_z', 0):+.4f} | "
                f"{pnl*100:+.4f}% | {bars} |"
            )
        lines.append("")

    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path


# ─── Main ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Paper Trader Report")
    parser.add_argument("--db-path", type=str, required=True, help="Path to the SQLite database (e.g. data/dev/trades_1m.db)")
    parser.add_argument("--min-sharpe", type=float, required=True, help="Minimum Sharpe ratio for Tier 1 filtering")
    parser.add_argument("--detailed", action="store_true", help="Show full trade log and signal quality")
    parser.add_argument("--pair", type=str, default=None, help='Single pair deep-dive (e.g. "MET/USDT|LTC/USDT")')
    parser.add_argument("--json", action="store_true", help="Output full report as JSON to stdout")
    parser.add_argument("--export", action="store_true", help="Save JSON + Markdown reports to data/ghost/reports/")
    args = parser.parse_args()

    state = GhostStateManager(db_path=args.db_path)

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
            # Also render to terminal
            render_executive_summary(report)
            return

        # Terminal rendering
        render_executive_summary(report)
        render_portfolio_metrics(report)
        render_per_pair(report, filter_pair=args.pair)

        if args.detailed or args.pair:
            render_trade_log(report, filter_pair=args.pair)
            render_signal_quality(report)

        render_risk(report)
        render_backtest_comparison(report)
        print()

    finally:
        state.close()


if __name__ == "__main__":
    main()
