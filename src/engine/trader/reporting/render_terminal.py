"""Terminal rendering for trader reports."""

from src.engine.trader.reporting.models import TradeReport


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
    if status == "DEGRADED":
        return f"{C.YELLOW}🟡 DEGRADED{C.RESET}"
    return f"{C.RED}🔴 FAILING{C.RESET}"


def _pnl_color(pnl: float) -> str:
    if pnl > 0:
        return f"{C.GREEN}{pnl*100:+.4f}%{C.RESET}"
    if pnl < 0:
        return f"{C.RED}{pnl*100:+.4f}%{C.RESET}"
    return f"{C.DIM}{pnl*100:+.4f}%{C.RESET}"


def _metric(label: str, value: str, width: int = 32) -> str:
    return f"  {C.DIM}{label + ':':<{width}}{C.RESET} {C.BOLD}{value}{C.RESET}"


def _header(title: str) -> None:
    line = "═" * 62
    print(f"\n{C.CYAN}{line}{C.RESET}")
    print(f"  {C.BOLD}{C.WHITE}{title}{C.RESET}")
    print(f"{C.CYAN}{line}{C.RESET}")


def _subheader(title: str) -> None:
    print(f"\n  {C.BLUE}── {title} ──{C.RESET}")


def render_executive_summary(report: TradeReport) -> None:
    _header("EXECUTIVE SUMMARY")
    print(_metric("Status", _status_color(report.status)))
    print(_metric("Total Equity", _pnl_color(report.total_equity_pct)))
    print(_metric("Realized PnL", _pnl_color(report.realized_pnl_pct)))
    print(_metric("Unrealized PnL", _pnl_color(report.unrealized_pnl_pct)))
    print(_metric("Active Pairs", str(report.active_pairs)))
    print(_metric("Total Trades", str(report.total_trades)))
    print(_metric("Uptime", f"{report.uptime_hours:.1f}h"))
    print(_metric("Bar Interval", f"{24*365/report.bars_per_year:.1f}h ({report.bars_per_year:.0f}/yr)"))


def render_portfolio_metrics(report: TradeReport) -> None:
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


def render_per_pair(report: TradeReport, filter_pair: str = None) -> None:
    _header("PER-PAIR BREAKDOWN")

    pairs = report.per_pair
    if filter_pair:
        pairs = [p for p in pairs if p.pair_label == filter_pair]
        if not pairs:
            print(f"  {C.RED}No data found for pair: {filter_pair}{C.RESET}")
            return

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


def render_trade_log(report: TradeReport, filter_pair: str = None) -> None:
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
        pnl = t.get("realized_pnl_pct") or 0.0
        marker = f"{C.GREEN}✓{C.RESET}" if pnl > 0 else f"{C.RED}✗{C.RESET}"
        bars = t.get("holding_bars") or "?"
        pnl_str = _pnl_color(pnl)
        entry_z = t.get("entry_z") or 0.0

        print(
            f"  {t.get('id', '?'):>4} {t.get('pair_label', '?'):<28} "
            f"{t.get('side', '?'):<14} {entry_z:>+8.4f} "
            f"{pnl_str:>20} {str(bars):>5} {marker:>6}"
        )


def render_signal_quality(report: TradeReport) -> None:
    _header("SIGNAL QUALITY")
    sq = report.signal_quality
    print(_metric("Signal Accuracy", f"{sq.signal_accuracy*100:.1f}%"))
    print(_metric("Avg Entry |Z|", f"{sq.avg_entry_z:.4f}"))
    exit_z_str = f"{sq.avg_exit_z:.4f}" if sq.avg_exit_z is not None else "N/A"
    print(_metric("Avg Exit |Z|", exit_z_str))
    print(_metric("False Signal Rate", f"{sq.false_signal_rate*100:.1f}%"))
    print(_metric("Total Signals Recorded", str(sq.total_signals_recorded)))


def render_risk(report: TradeReport) -> None:
    _header("RISK DASHBOARD")
    r = report.risk
    print(_metric("Portfolio Heat", f"{r.portfolio_heat*100:.4f}%"))
    print(_metric("Largest Unrealized Loss", _pnl_color(r.largest_single_loss)))
    print(_metric("Days Since Last Trade", f"{r.days_since_last_trade:.1f}"))
    print(_metric("Consecutive Losses", str(r.consecutive_losses)))
    print(_metric("Data Freshness", r.data_freshness[:19] if len(r.data_freshness) > 10 else r.data_freshness))


def render_state_ledger(report: TradeReport) -> None:
    _header("STATE LEDGER")
    ledger = report.state_ledger
    latest_recon = ledger.latest_reconciliation_run_status or "N/A"

    print(_metric("Order Events", str(ledger.total_order_events)))
    print(_metric("Reconciliation Status", latest_recon))
    print(_metric("Reconciliation Deltas", str(ledger.reconciliation_delta_count)))

    _subheader("Leg Order Statuses")
    if not ledger.leg_targets_by_status_role:
        print(f"  {C.DIM}No leg order rows recorded.{C.RESET}")
    else:
        for status, role_counts in ledger.leg_targets_by_status_role.items():
            role_summary = ", ".join(
                f"{role}: {count}" for role, count in role_counts.items()
            )
            print(_metric(status, role_summary))

    _subheader("User Commands")
    if not ledger.user_commands_by_status:
        print(f"  {C.DIM}No user commands recorded.{C.RESET}")
    else:
        for status, count in ledger.user_commands_by_status.items():
            print(_metric(status, str(count)))


def render_backtest_comparison(report: TradeReport) -> None:
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

    if report.sharpe_ratio is not None and report.backtest_avg_sharpe is not None and report.backtest_avg_sharpe > 0:
        ratio = report.sharpe_ratio / report.backtest_avg_sharpe
        if ratio >= 0.5:
            verdict = f"{C.GREEN}VALIDATED (Live/BT = {ratio:.2f}){C.RESET}"
        elif ratio >= 0.3:
            verdict = f"{C.YELLOW}INVESTIGATE (Live/BT = {ratio:.2f}){C.RESET}"
        else:
            verdict = f"{C.RED}BROKEN (Live/BT = {ratio:.2f}){C.RESET}"
        print(f"\n  {C.BOLD}Verdict:{C.RESET} {verdict}")
