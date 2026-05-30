"""Durable risk kill-switch state for runtime entry gating."""

from datetime import datetime, timezone
from typing import Any, Protocol

from src.engine.trader.runtime.risk.models import RiskKillSwitchState


RISK_KILL_SWITCH_KEY = "risk.kill_switch"


class RuntimeStateStore(Protocol):
    """Small runtime-state interface used by risk controls."""

    def set_runtime_state(self, key: str, value: Any) -> None:
        """Persist one runtime state value."""

    def get_runtime_state(self, key: str, default: Any = None) -> Any:
        """Read one runtime state value."""


def get_risk_kill_switch_state(state: RuntimeStateStore) -> RiskKillSwitchState:
    """Read the durable risk kill-switch state."""
    raw = state.get_runtime_state(RISK_KILL_SWITCH_KEY, default=None)
    if not isinstance(raw, dict):
        return RiskKillSwitchState(active=False)
    active = raw.get("active")
    if not isinstance(active, bool):
        return RiskKillSwitchState(active=False)
    reason = raw.get("reason")
    activated_at = raw.get("activated_at")
    return RiskKillSwitchState(
        active=active,
        reason=reason if isinstance(reason, str) and reason else None,
        activated_at=activated_at if isinstance(activated_at, str) and activated_at else None,
    )


def activate_risk_kill_switch(
    state: RuntimeStateStore,
    *,
    reason: str,
    activated_at: str | None = None,
) -> RiskKillSwitchState:
    """Persist an active risk kill-switch state."""
    if not reason:
        raise ValueError("risk kill-switch reason must be non-empty")
    switch_state = RiskKillSwitchState(
        active=True,
        reason=reason,
        activated_at=activated_at or datetime.now(timezone.utc).isoformat(),
    )
    state.set_runtime_state(RISK_KILL_SWITCH_KEY, _serialize(switch_state))
    return switch_state


def clear_risk_kill_switch(state: RuntimeStateStore) -> RiskKillSwitchState:
    """Persist an inactive risk kill-switch state."""
    switch_state = RiskKillSwitchState(active=False)
    state.set_runtime_state(RISK_KILL_SWITCH_KEY, _serialize(switch_state))
    return switch_state


def _serialize(state: RiskKillSwitchState) -> dict[str, object]:
    return {
        "active": state.active,
        "reason": state.reason,
        "activated_at": state.activated_at,
    }
