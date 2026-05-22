"""Trader runtime health snapshots for operator visibility."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.engine.trader.state.manager import TradeStateManager


@dataclass(frozen=True)
class TraderHealthSnapshot:
    environment: str
    status: str
    open_positions: int
    system_paused: bool
    latest_tick_at: str | None
    latest_tick_age_minutes: float | None
    latest_equity_at: str | None
    total_equity_pct: float | None
    realized_pnl_pct: float | None
    unrealized_pnl_pct: float | None
    latest_reconciliation_status: str | None
    reconciliation_delta_count: int


def render_trader_health_snapshot(
    snapshot: TraderHealthSnapshot,
    *,
    title: str = "TRADER HEALTH",
) -> str:
    """Render a compact HTML health snapshot for operator notifications."""
    age = (
        f"{snapshot.latest_tick_age_minutes:.1f}m"
        if snapshot.latest_tick_age_minutes is not None
        else "N/A"
    )
    paused = "YES" if snapshot.system_paused else "NO"
    recon = snapshot.latest_reconciliation_status or "N/A"
    return (
        f"🩺 <b>{title}</b>\n"
        f"Mode: {snapshot.environment}\n"
        f"Status: <b>{snapshot.status}</b>\n"
        f"Open Positions: {snapshot.open_positions}\n"
        f"Paused: {paused}\n"
        f"Latest Tick: {snapshot.latest_tick_at or 'N/A'}\n"
        f"Tick Age: {age}\n"
        f"Equity: {_format_pct(snapshot.total_equity_pct)}\n"
        f"Realized: {_format_pct(snapshot.realized_pnl_pct)}\n"
        f"Unrealized: {_format_pct(snapshot.unrealized_pnl_pct)}\n"
        f"Reconciliation: {recon} | Deltas: {snapshot.reconciliation_delta_count}"
    )


def build_trader_health_snapshot(
    state: TradeStateManager,
    *,
    environment: str,
    stale_after_minutes: float,
    now: datetime | None = None,
) -> TraderHealthSnapshot:
    """Build a read-only health snapshot from persisted runtime state."""
    reference_time = now or datetime.now(timezone.utc)
    latest_signal = _latest_by_timestamp(state.get_tick_signals())
    latest_tick_at = latest_signal.get("timestamp") if latest_signal else None
    latest_tick_age_minutes = _age_minutes(latest_tick_at, reference_time)

    equity = state.get_equity_curve()
    latest_equity = equity[-1] if equity else None
    latest_equity_at = latest_equity.get("timestamp") if latest_equity else None

    reconciliation_runs = state.get_reconciliation_runs()
    latest_reconciliation = reconciliation_runs[-1] if reconciliation_runs else None
    latest_run_id = latest_reconciliation.get("id") if latest_reconciliation else None
    reconciliation_delta_count = (
        len(state.get_reconciliation_deltas(run_id=latest_run_id))
        if latest_run_id is not None
        else 0
    )

    status = _classify_status(
        latest_tick_age_minutes=latest_tick_age_minutes,
        stale_after_minutes=stale_after_minutes,
        latest_reconciliation_status=(
            latest_reconciliation.get("status") if latest_reconciliation else None
        ),
        reconciliation_delta_count=reconciliation_delta_count,
    )

    return TraderHealthSnapshot(
        environment=environment,
        status=status,
        open_positions=len(state.get_open_positions()),
        system_paused=state.is_system_paused(),
        latest_tick_at=latest_tick_at,
        latest_tick_age_minutes=latest_tick_age_minutes,
        latest_equity_at=latest_equity_at,
        total_equity_pct=_optional_float(latest_equity, "total_equity_pct"),
        realized_pnl_pct=_optional_float(latest_equity, "realized_pnl_pct"),
        unrealized_pnl_pct=_optional_float(latest_equity, "unrealized_pnl_pct"),
        latest_reconciliation_status=(
            latest_reconciliation.get("status") if latest_reconciliation else None
        ),
        reconciliation_delta_count=reconciliation_delta_count,
    )


def _classify_status(
    *,
    latest_tick_age_minutes: float | None,
    stale_after_minutes: float,
    latest_reconciliation_status: str | None,
    reconciliation_delta_count: int,
) -> str:
    if latest_tick_age_minutes is None:
        return "NO_TICKS"
    if latest_tick_age_minutes > stale_after_minutes:
        return "STALE"
    if reconciliation_delta_count > 0:
        return "RECONCILIATION_DELTAS"
    if latest_reconciliation_status not in (None, "MATCHED"):
        return "RECONCILIATION_WARNING"
    return "HEALTHY"


def _latest_by_timestamp(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return max(rows, key=lambda row: row.get("timestamp") or "")


def _age_minutes(timestamp: str | None, now: datetime) -> float | None:
    parsed = _parse_timestamp(timestamp)
    if parsed is None:
        return None
    return max(0.0, (now - parsed).total_seconds() / 60.0)


def _parse_timestamp(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _optional_float(row: dict[str, Any] | None, key: str) -> float | None:
    if row is None:
        return None
    value = row.get(key)
    return float(value) if value is not None else None


def _format_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:+.4f}%"
