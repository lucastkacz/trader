"""Read-only runtime drill status for operator visibility."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from src.engine.trader.reporting.assembler import generate_report
from src.engine.trader.runtime.monitoring.health import (
    TraderHealthSnapshot,
    build_trader_health_snapshot,
)
from src.engine.trader.state.manager import TradeStateManager

OBSERVER_RUN_STATE_KEY = "observer_run"


@dataclass(frozen=True)
class RunStatusSnapshot:
    environment: str
    observer_status: str
    observer_detail: str
    health: TraderHealthSnapshot
    closed_positions: int
    open_position_ids: list[int]
    state_only_identifier_count: int
    report_json_status: str


def record_observer_run_started(
    state: TradeStateManager,
    *,
    max_ticks: int | None,
    started_at: datetime | None = None,
) -> None:
    """Persist that an observer run is actively evaluating ticks."""
    state.set_runtime_state(
        OBSERVER_RUN_STATE_KEY,
        {
            "status": "RUNNING",
            "started_at": _timestamp(started_at),
            "max_ticks": max_ticks,
            "completed_ticks": 0,
            "completed_at": None,
            "open_position_ids": [],
        },
    )


def record_observer_max_ticks_completed(
    state: TradeStateManager,
    *,
    max_ticks: int,
    completed_ticks: int,
    open_position_ids: list[int],
    completed_at: datetime | None = None,
) -> None:
    """Persist a clean bounded-drill stop after max_ticks."""
    state.set_runtime_state(
        OBSERVER_RUN_STATE_KEY,
        {
            "status": "COMPLETED_MAX_TICKS",
            "started_at": _current_run_value(state, "started_at"),
            "max_ticks": max_ticks,
            "completed_ticks": completed_ticks,
            "completed_at": _timestamp(completed_at),
            "open_position_ids": open_position_ids,
        },
    )


def record_observer_run_failed(
    state: TradeStateManager,
    *,
    reason: str,
    failed_at: datetime | None = None,
) -> None:
    """Persist that the observer exited unexpectedly."""
    state.set_runtime_state(
        OBSERVER_RUN_STATE_KEY,
        {
            "status": "FAILED",
            "started_at": _current_run_value(state, "started_at"),
            "max_ticks": _current_run_value(state, "max_ticks"),
            "completed_ticks": _current_run_value(state, "completed_ticks"),
            "failed_at": _timestamp(failed_at),
            "reason": reason,
            "open_position_ids": _open_position_ids(state),
        },
    )


def record_observer_run_interrupted(
    state: TradeStateManager,
    *,
    interrupted_at: datetime | None = None,
) -> None:
    """Persist an operator/local interruption distinct from max tick completion."""
    state.set_runtime_state(
        OBSERVER_RUN_STATE_KEY,
        {
            "status": "INTERRUPTED",
            "started_at": _current_run_value(state, "started_at"),
            "max_ticks": _current_run_value(state, "max_ticks"),
            "completed_ticks": _current_run_value(state, "completed_ticks"),
            "interrupted_at": _timestamp(interrupted_at),
            "open_position_ids": _open_position_ids(state),
        },
    )


def build_run_status_snapshot(
    state: TradeStateManager,
    *,
    environment: str,
    stale_after_minutes: float,
    surviving_pairs_path: Path,
    report_min_sharpe: float = 0.0,
    now: datetime | None = None,
) -> RunStatusSnapshot:
    """Build an operator drill snapshot from persisted runtime state only."""
    health = build_trader_health_snapshot(
        state,
        environment=environment,
        stale_after_minutes=stale_after_minutes,
        now=now,
    )
    run_marker = _observer_run_marker(state)
    open_position_ids = _open_position_ids(state)
    observer_status, observer_detail = _classify_observer_status(
        health=health,
        run_marker=run_marker,
    )

    return RunStatusSnapshot(
        environment=environment,
        observer_status=observer_status,
        observer_detail=observer_detail,
        health=health,
        closed_positions=len(state.get_all_closed()),
        open_position_ids=open_position_ids,
        state_only_identifier_count=_state_only_identifier_count(state),
        report_json_status=_report_json_status(
            state,
            surviving_pairs_path=surviving_pairs_path,
            min_sharpe=report_min_sharpe,
        ),
    )


def _classify_observer_status(
    *,
    health: TraderHealthSnapshot,
    run_marker: dict[str, Any] | None,
) -> tuple[str, str]:
    marker_status = run_marker.get("status") if run_marker else None

    if marker_status == "COMPLETED_MAX_TICKS":
        max_ticks = run_marker.get("max_ticks")
        open_ids = run_marker.get("open_position_ids") or []
        return (
            "CLEANLY_STOPPED_MAX_TICKS",
            f"Completed {max_ticks} ticks; open local positions at stop: {len(open_ids)}.",
        )
    if marker_status == "FAILED":
        return "STOPPED_UNEXPECTEDLY", str(run_marker.get("reason") or "unknown error")
    if marker_status == "INTERRUPTED":
        return "INTERRUPTED", "Observer was interrupted before natural completion."
    if health.status == "STALE":
        return "STALE_UNEXPECTEDLY", "Latest tick is older than the configured stale window."
    if marker_status == "RUNNING" and health.status != "NO_TICKS":
        return "RUNNING_FRESH", "Observer has recent persisted tick state."
    if marker_status == "RUNNING":
        return "RUNNING_WAITING_FOR_FIRST_TICK", "Observer boot marker exists; no tick recorded yet."
    if health.status == "NO_TICKS":
        return "NO_TICKS", "No persisted tick signals found."
    return "FRESH_NO_RUN_MARKER", "Runtime state is fresh, but no observer run marker was found."


def _observer_run_marker(state: TradeStateManager) -> dict[str, Any] | None:
    marker = state.get_runtime_state(OBSERVER_RUN_STATE_KEY, None)
    return marker if isinstance(marker, dict) else None


def _current_run_value(state: TradeStateManager, key: str) -> Any:
    marker = _observer_run_marker(state)
    return marker.get(key) if marker else None


def _open_position_ids(state: TradeStateManager) -> list[int]:
    return [int(position["id"]) for position in state.get_open_positions()]


def _state_only_identifier_count(state: TradeStateManager) -> int:
    return sum(
        1
        for leg in state.get_leg_fills()
        if leg.get("exchange_order_id") is not None
        or leg.get("client_order_id") is not None
    )


def _report_json_status(
    state: TradeStateManager,
    *,
    surviving_pairs_path: Path,
    min_sharpe: float,
) -> str:
    try:
        report = generate_report(
            state,
            min_sharpe=min_sharpe,
            surviving_pairs_path=str(surviving_pairs_path),
        )
        json.loads(json.dumps(report.to_dict(), default=str))
    except FileNotFoundError:
        return "MISSING_ARTIFACT"
    except Exception as exc:
        return f"ERROR: {exc}"
    return "OK"


def _timestamp(value: datetime | None = None) -> str:
    timestamp = value or datetime.now(timezone.utc)
    return timestamp.astimezone(timezone.utc).isoformat()
