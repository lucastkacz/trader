"""
Tests for GhostStateManager.
Uses in-memory SQLite to avoid filesystem side effects.
"""

import pytest
from src.engine.ghost.state_manager import GhostStateManager


@pytest.fixture
def state():
    """Create a fresh in-memory state manager for each test."""
    mgr = GhostStateManager(db_path=":memory:")
    yield mgr
    mgr.close()


def test_open_and_retrieve_position(state):
    """Opening a ghost position should be retrievable."""
    row_id = state.open_position(
        pair_label="AAA/USDT|BBB/USDT",
        asset_x="AAA/USDT",
        asset_y="BBB/USDT",
        side="LONG_SPREAD",
        entry_price_a=100.0,
        entry_price_b=50.0,
        weight_a=0.6,
        weight_b=0.4,
        entry_z=-2.5,
        lookback_days=14,
    )

    assert row_id == 1
    pos = state.get_position_for_pair("AAA/USDT|BBB/USDT")
    assert pos is not None
    assert pos["side"] == "LONG_SPREAD"
    assert pos["entry_price_a"] == 100.0
    assert pos["status"] == "OPEN"


def test_close_position_calculates_pnl(state):
    """Closing a LONG_SPREAD position should calculate correct PnL."""
    state.open_position(
        pair_label="X/USDT|Y/USDT",
        asset_x="X/USDT",
        asset_y="Y/USDT",
        side="LONG_SPREAD",
        entry_price_a=100.0,
        entry_price_b=50.0,
        weight_a=0.5,
        weight_b=0.5,
        entry_z=-2.0,
        lookback_days=21,
    )

    # A goes up 10%, B stays flat → net PnL = 0.5 * 0.10 - 0.5 * 0.0 = +5%
    pnl = state.close_position("X/USDT|Y/USDT", exit_price_a=110.0, exit_price_b=50.0)
    assert pnl is not None
    assert abs(pnl - 0.05) < 1e-10

    # Position should now be closed
    pos = state.get_position_for_pair("X/USDT|Y/USDT")
    assert pos is None

    closed = state.get_all_closed()
    assert len(closed) == 1
    assert closed[0]["status"] == "CLOSED"


def test_close_short_spread_pnl(state):
    """Closing a SHORT_SPREAD: A goes down, B goes up → profitable."""
    state.open_position(
        pair_label="X/USDT|Y/USDT",
        asset_x="X/USDT",
        asset_y="Y/USDT",
        side="SHORT_SPREAD",
        entry_price_a=100.0,
        entry_price_b=50.0,
        weight_a=0.5,
        weight_b=0.5,
        entry_z=2.0,
        lookback_days=7,
    )

    # A goes down 10% (good for short A), B goes up 10% (good for long B)
    # PnL = -0.5 * (-0.10) + 0.5 * 0.10 = 0.05 + 0.05 = 0.10
    pnl = state.close_position("X/USDT|Y/USDT", exit_price_a=90.0, exit_price_b=55.0)
    assert pnl is not None
    assert abs(pnl - 0.10) < 1e-10


def test_close_nonexistent_position_returns_none(state):
    """Closing a pair with no open position returns None."""
    result = state.close_position("FAKE/USDT|PAIR/USDT", 100.0, 50.0)
    assert result is None


def test_equity_snapshot(state):
    """Equity snapshots should be written and retrievable."""
    state.snapshot_equity(
        total_equity_pct=0.05,
        open_positions=3,
        realized_pnl_pct=0.02,
        unrealized_pnl_pct=0.03,
    )

    snapshots = state.get_equity_curve()
    assert len(snapshots) == 1
    assert snapshots[0]["total_equity_pct"] == 0.05
    assert snapshots[0]["open_positions"] == 3


def test_multiple_positions_tracked(state):
    """Multiple pairs can have open positions simultaneously."""
    state.open_position("A|B", "A", "B", "LONG_SPREAD", 10, 5, 0.5, 0.5, -2.0, 14)
    state.open_position("C|D", "C", "D", "SHORT_SPREAD", 20, 10, 0.6, 0.4, 2.0, 7)

    open_pos = state.get_open_positions()
    assert len(open_pos) == 2

    # Close one
    state.close_position("A|B", 11, 5)
    open_pos = state.get_open_positions()
    assert len(open_pos) == 1
    assert open_pos[0]["pair_label"] == "C|D"
