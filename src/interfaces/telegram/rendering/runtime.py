"""Telegram runtime status renderers."""

import html

from src.engine.trader.runtime.run_status import RunStatusSnapshot
from src.interfaces.telegram.rendering.formatting import format_age_minutes


def render_run_status(snapshot: RunStatusSnapshot) -> str:
    """Render the local observer/drill status as a Telegram HTML message."""
    open_ids = (
        ", ".join(f"#{position_id}" for position_id in snapshot.open_position_ids)
        if snapshot.open_position_ids
        else "none"
    )
    paused = "YES" if snapshot.health.system_paused else "NO"
    safety = (
        "PASS"
        if snapshot.state_only_identifier_count == 0
        else f"INVESTIGATE ({snapshot.state_only_identifier_count})"
    )
    return (
        "🧭 <b>RUN STATUS</b>\n"
        f"Mode: {html.escape(snapshot.environment)}\n"
        f"Observer: <b>{html.escape(snapshot.observer_status)}</b>\n"
        f"{html.escape(snapshot.observer_detail)}\n\n"
        f"Health: {html.escape(snapshot.health.status)}\n"
        f"Latest Tick: {snapshot.health.latest_tick_at or 'N/A'}\n"
        f"Tick Age: {format_age_minutes(snapshot.health.latest_tick_age_minutes)}\n"
        f"Paused: {paused}\n\n"
        f"Open Positions: {snapshot.health.open_positions}\n"
        f"Closed Positions: {snapshot.closed_positions}\n"
        f"Open IDs: {open_ids}\n\n"
        f"State-only order-id invariant: {safety}\n"
        f"Reconciliation: {snapshot.health.latest_reconciliation_status or 'N/A'} | "
        f"Deltas: {snapshot.health.reconciliation_delta_count}\n"
        f"Report JSON parse: {html.escape(snapshot.report_json_status)}"
    )
