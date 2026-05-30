"""Markdown rendering for trader reports."""

from src.engine.trader.reporting.models import TradeReport


def render_markdown(report: TradeReport) -> str:
    """Render a report as Markdown text."""
    week_num = 1
    if report.uptime_hours > 0:
        week_num = max(1, int(report.uptime_hours / (24 * 7)) + 1)

    lines = []
    lines.append(f"# Trader Report — Week {week_num}")
    lines.append(f"*Generated: {report.report_timestamp[:19]} UTC*\n")

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

    lines.append("## State Ledger\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Order Events | {report.state_ledger.total_order_events} |")
    latest_recon = report.state_ledger.latest_reconciliation_run_status or "N/A"
    lines.append(f"| Latest Reconciliation Status | {latest_recon} |")
    lines.append(f"| Latest Reconciliation Deltas | {report.state_ledger.reconciliation_delta_count} |")
    lines.append(f"| Historical Reconciliation Deltas | {report.state_ledger.total_reconciliation_delta_count} |")
    lines.append("")

    lines.append("### Leg Order Statuses\n")
    lines.append("| Status | Roles |")
    lines.append("|--------|-------|")
    if report.state_ledger.leg_targets_by_status_role:
        for status, role_counts in report.state_ledger.leg_targets_by_status_role.items():
            role_summary = ", ".join(
                f"{role}: {count}" for role, count in role_counts.items()
            )
            lines.append(f"| {status} | {role_summary} |")
    else:
        lines.append("| N/A | No leg order rows recorded. |")
    lines.append("")

    lines.append("### User Commands\n")
    lines.append("| Status | Count |")
    lines.append("|--------|-------|")
    if report.state_ledger.user_commands_by_status:
        for status, count in report.state_ledger.user_commands_by_status.items():
            lines.append(f"| {status} | {count} |")
    else:
        lines.append("| N/A | 0 |")
    lines.append("")

    lines.append("## Portfolio Metrics\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
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

    if report.pair_validity is not None:
        lines.append("## Pair Validity Diagnostics\n")
        if report.pair_validity.notes:
            for note in report.pair_validity.notes:
                lines.append(f"- {note}")
            lines.append("")
        if report.pair_validity.snapshots:
            lines.append(
                "| Pair | Bars Since Artifact | Hedge Drift | Corr Recent/Research | "
                "P Recent/Research | Half-Life Drift | Review Reasons |"
            )
            lines.append(
                "|------|---------------------|-------------|----------------------|"
                "-------------------|-----------------|----------------|"
            )
            for snapshot in report.pair_validity.snapshots:
                reasons = (
                    snapshot.operator_review_reasons
                    + snapshot.open_position_review_reasons
                )
                reason_text = ", ".join(reasons) if reasons else "none"
                lines.append(
                    f"| {snapshot.pair_label} | "
                    f"{_fmt_int(snapshot.bars_since_artifact_generation)} | "
                    f"{_fmt_pct(snapshot.hedge_ratio_drift_pct)} | "
                    f"{_fmt_pair(snapshot.recent_correlation, snapshot.research_correlation)} | "
                    f"{_fmt_pair(snapshot.recent_p_value, snapshot.research_p_value)} | "
                    f"{_fmt_pct(snapshot.half_life_drift_pct)} | "
                    f"{reason_text} |"
                )
            lines.append("")

    if report.pair_queue is not None:
        lines.append("## Dynamic Pair Queue\n")
        lines.append(
            "| Rank | Pair | Entry Allowed | Total | Research | Validity | "
            "Opportunity | Blocks | Review |"
        )
        lines.append(
            "|------|------|---------------|-------|----------|----------|"
            "-------------|--------|--------|"
        )
        for decision in report.pair_queue.decisions:
            blocks = ", ".join(decision.block_reasons) if decision.block_reasons else "none"
            review = ", ".join(decision.review_reasons) if decision.review_reasons else "none"
            lines.append(
                f"| {decision.current_rank} | {decision.pair_label} | "
                f"{'yes' if decision.entry_allowed else 'no'} | "
                f"{decision.score_total:.3f} | {decision.score_research:.3f} | "
                f"{decision.score_validity:.3f} | {decision.score_opportunity:.3f} | "
                f"{blocks} | {review} |"
            )
        lines.append("")

    if report.trade_log:
        lines.append("## Trade Log\n")
        lines.append("| ID | Pair | Side | Entry Z | PnL% | Bars |")
        lines.append("|----|------|------|---------|------|------|")
        for t in report.trade_log:
            pnl = t.get("realized_pnl_pct") or 0.0
            bars = t.get("holding_bars") or "?"
            lines.append(
                f"| {t.get('id', '?')} | {t.get('pair_label', '?')} | "
                f"{t.get('side', '?')} | {t.get('entry_z', 0):+.4f} | "
                f"{pnl*100:+.4f}% | {bars} |"
            )
        lines.append("")

    return "\n".join(lines)


def _fmt(value: float | None, fmt: str = ".4f") -> str:
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
