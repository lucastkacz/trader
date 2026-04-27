"""State ledger report metrics."""

from typing import Any

from src.engine.trader.reporting.models import StateLedgerSnapshot


def _count_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    """Return deterministic counts for a single row field."""
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get(key) or "UNKNOWN"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _count_leg_targets_by_status_role(
    leg_fills: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Count leg target/fill rows by status, then role."""
    counts: dict[str, dict[str, int]] = {}
    for row in leg_fills:
        status = row.get("status") or "UNKNOWN"
        role = row.get("leg_role") or "UNKNOWN"
        role_counts = counts.setdefault(status, {})
        role_counts[role] = role_counts.get(role, 0) + 1

    return {
        status: dict(sorted(role_counts.items()))
        for status, role_counts in sorted(counts.items())
    }


def _compute_state_ledger(
    order_events: list[dict[str, Any]],
    leg_fills: list[dict[str, Any]],
    user_commands: list[dict[str, Any]],
    reconciliation_runs: list[dict[str, Any]],
    reconciliation_deltas: list[dict[str, Any]],
) -> StateLedgerSnapshot:
    """Summarize state-ledger tables without changing trader state."""
    latest_run_status = None
    if reconciliation_runs:
        latest_run_status = reconciliation_runs[-1].get("status")

    return StateLedgerSnapshot(
        total_order_events=len(order_events),
        leg_targets_by_status_role=_count_leg_targets_by_status_role(leg_fills),
        user_commands_by_status=_count_by_key(user_commands, "status"),
        latest_reconciliation_run_status=latest_run_status,
        reconciliation_delta_count=len(reconciliation_deltas),
    )
