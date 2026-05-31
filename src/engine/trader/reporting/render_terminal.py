"""Terminal rendering for trader reports."""

from src.engine.trader.reporting.models import TradeReport
from src.engine.trader.runtime.pair_queue import PairQueueValidityThresholdEvidence


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


def _format_bar_interval(bars_per_year: float) -> str:
    interval_hours = 24 * 365 / bars_per_year
    if interval_hours < 1.0:
        return f"{interval_hours * 60:.1f}m ({bars_per_year:.0f}/yr)"
    return f"{interval_hours:.1f}h ({bars_per_year:.0f}/yr)"


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
    print(_metric("Bar Interval", _format_bar_interval(report.bars_per_year)))


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
    print(_metric("Latest Reconciliation Deltas", str(ledger.reconciliation_delta_count)))
    print(_metric("Historical Reconciliation Deltas", str(ledger.total_reconciliation_delta_count)))
    for delta_type, count in ledger.latest_reconciliation_deltas_by_type.items():
        print(_metric(delta_type, str(count)))

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


def render_pair_validity(report: TradeReport, filter_pair: str = None) -> None:
    _header("PAIR VALIDITY DIAGNOSTICS")
    validity = report.pair_validity
    if validity is None:
        print(f"  {C.DIM}Not requested. Pass market-data diagnostics inputs to enable.{C.RESET}")
        return
    if validity.notes:
        for note in validity.notes:
            print(f"  {C.YELLOW}{note}{C.RESET}")
        if not validity.snapshots:
            return

    snapshots = validity.snapshots
    if filter_pair:
        snapshots = [snapshot for snapshot in snapshots if snapshot.pair_label == filter_pair]
        if not snapshots:
            print(f"  {C.RED}No pair-validity data found for pair: {filter_pair}{C.RESET}")
            return

    print(
        f"  {C.DIM}{'Pair':<30} {'Bars':>7} {'HR Drift':>10} "
        f"{'Corr':>9} {'P-Value':>9} {'HL Drift':>10} {'Review':>8}{C.RESET}"
    )
    print(
        f"  {C.DIM}{'─'*30} {'─'*7} {'─'*10} "
        f"{'─'*9} {'─'*9} {'─'*10} {'─'*8}{C.RESET}"
    )

    for snapshot in snapshots:
        review_count = (
            len(snapshot.operator_review_reasons)
            + len(snapshot.open_position_review_reasons)
        )
        review = f"{C.YELLOW}{review_count}{C.RESET}" if review_count else f"{C.GREEN}0{C.RESET}"
        print(
            f"  {snapshot.pair_label:<30} "
            f"{_fmt_int(snapshot.bars_since_artifact_generation):>7} "
            f"{_fmt_pct(snapshot.hedge_ratio_drift_pct):>10} "
            f"{_fmt_pair(snapshot.recent_correlation, snapshot.research_correlation):>9} "
            f"{_fmt_pair(snapshot.recent_p_value, snapshot.research_p_value):>9} "
            f"{_fmt_pct(snapshot.half_life_drift_pct):>10} "
            f"{review:>17}"
        )
        if snapshot.open_position_id is not None:
            multiple = _fmt_float(snapshot.open_position_half_life_multiple, ".2f")
            print(
                f"  {C.DIM}  └─ Open #{snapshot.open_position_id}: "
                f"{_fmt_int(snapshot.open_position_holding_bars)} bars, "
                f"{multiple}x research half-life{C.RESET}"
            )
        reasons = snapshot.operator_review_reasons + snapshot.open_position_review_reasons
        if reasons:
            print(f"  {C.DIM}  └─ Review: {', '.join(reasons)}{C.RESET}")
        if snapshot.notes:
            print(f"  {C.DIM}  └─ Notes: {', '.join(snapshot.notes)}{C.RESET}")


def render_pair_queue(report: TradeReport, filter_pair: str = None) -> None:
    _header("DYNAMIC PAIR QUEUE")
    queue = report.pair_queue
    if queue is None:
        print(f"  {C.DIM}Not requested. Pair-validity diagnostics are required.{C.RESET}")
        return

    decisions = queue.decisions
    if filter_pair:
        decisions = [decision for decision in decisions if decision.pair_label == filter_pair]
        if not decisions:
            print(f"  {C.RED}No pair-queue decision found for pair: {filter_pair}{C.RESET}")
            return

    print(
        f"  {C.DIM}{'Rank':>4} {'Pair':<30} {'Entry':>7} {'Total':>7} "
        f"{'Rsrch':>7} {'Valid':>7} {'Opp':>7} {'Blocks':>7}{C.RESET}"
    )
    print(
        f"  {C.DIM}{'─'*4} {'─'*30} {'─'*7} {'─'*7} "
        f"{'─'*7} {'─'*7} {'─'*7} {'─'*7}{C.RESET}"
    )

    for decision in decisions:
        entry = f"{C.GREEN}YES{C.RESET}" if decision.entry_allowed else f"{C.RED}NO{C.RESET}"
        print(
            f"  {decision.current_rank:>4} {decision.pair_label:<30} "
            f"{entry:>16} {decision.score_total:>7.3f} "
            f"{decision.score_research:>7.3f} {decision.score_validity:>7.3f} "
            f"{decision.score_opportunity:>7.3f} {len(decision.block_reasons):>7}"
        )
        if decision.research_rank != decision.current_rank:
            print(
                f"  {C.DIM}  └─ Research rank: #{decision.research_rank}{C.RESET}"
            )
        if decision.block_reasons:
            print(f"  {C.DIM}  └─ Blocks: {', '.join(decision.block_reasons)}{C.RESET}")
        if decision.review_reasons:
            print(f"  {C.DIM}  └─ Review: {', '.join(decision.review_reasons)}{C.RESET}")
        triggered_thresholds = [
            _fmt_threshold_evidence(evidence)
            for evidence in decision.validity_threshold_evidence
            if evidence.triggered
        ]
        if triggered_thresholds:
            print(f"  {C.DIM}  └─ Thresholds: {', '.join(triggered_thresholds)}{C.RESET}")
        if decision.notes:
            print(f"  {C.DIM}  └─ Notes: {', '.join(decision.notes)}{C.RESET}")


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


def _fmt_float(value: float | None, fmt: str = ".4f") -> str:
    return f"{value:{fmt}}" if value is not None else "N/A"


def _fmt_int(value: int | None) -> str:
    return str(value) if value is not None else "N/A"


def _fmt_pct(value: float | None) -> str:
    return f"{value:+.1f}%" if value is not None else "N/A"


def _fmt_pair(recent: float | None, research: float | None) -> str:
    if recent is None:
        return "N/A"
    if research is None:
        return f"{recent:.3f}"
    return f"{recent:.3f}/{research:.3f}"


def _fmt_threshold_evidence(evidence: PairQueueValidityThresholdEvidence) -> str:
    return (
        f"{evidence.metric}={evidence.measured_value:g} "
        f"{evidence.trigger_condition} {evidence.configured_threshold:g}"
    )
