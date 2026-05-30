import pytest

from src.engine.trader.runtime.risk import (
    activate_risk_kill_switch,
    clear_risk_kill_switch,
    get_risk_kill_switch_state,
)
from src.engine.trader.runtime.risk.kill_switch import RISK_KILL_SWITCH_KEY
from src.engine.trader.state.manager import TradeStateManager


@pytest.fixture
def state():
    mgr = TradeStateManager(db_path=":memory:")
    yield mgr
    mgr.close()


def test_risk_kill_switch_defaults_to_inactive(state):
    switch_state = get_risk_kill_switch_state(state)

    assert switch_state.active is False
    assert switch_state.reason is None
    assert switch_state.activated_at is None


def test_activate_and_clear_risk_kill_switch_persist_typed_state(state):
    activated = activate_risk_kill_switch(
        state,
        reason="operator review",
        activated_at="2026-05-29T00:00:00+00:00",
    )

    assert activated.active is True
    assert get_risk_kill_switch_state(state) == activated

    cleared = clear_risk_kill_switch(state)

    assert cleared.active is False
    assert get_risk_kill_switch_state(state) == cleared


def test_risk_kill_switch_ignores_malformed_runtime_state(state):
    state.set_runtime_state(
        RISK_KILL_SWITCH_KEY,
        {"active": "yes", "reason": ["not", "typed"]},
    )

    switch_state = get_risk_kill_switch_state(state)

    assert switch_state.active is False
    assert switch_state.reason is None
    assert switch_state.activated_at is None


def test_activate_risk_kill_switch_requires_reason(state):
    with pytest.raises(ValueError, match="reason"):
        activate_risk_kill_switch(state, reason="")
