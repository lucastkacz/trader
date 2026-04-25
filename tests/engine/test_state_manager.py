"""
Tests for GhostStateManager.
Uses in-memory SQLite to avoid filesystem side effects.
"""

import json
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
        lookback_bars=14,
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
        lookback_bars=21,
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
        lookback_bars=7,
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


# ─── New Tests: Schema Enhancement ──────────────────────────────

def test_close_position_with_exit_z(state):
    """Closing with exit_z should store the Z-score at exit."""
    state.open_position(
        pair_label="X/USDT|Y/USDT",
        asset_x="X/USDT",
        asset_y="Y/USDT",
        side="LONG_SPREAD",
        entry_price_a=100.0,
        entry_price_b=50.0,
        weight_a=0.5,
        weight_b=0.5,
        entry_z=-2.5,
        lookback_bars=14,
    )

    pnl = state.close_position(
        "X/USDT|Y/USDT",
        exit_price_a=110.0,
        exit_price_b=50.0,
        exit_z=0.15,
    )
    assert pnl is not None

    closed = state.get_all_closed()
    assert len(closed) == 1
    assert closed[0]["exit_z"] == 0.15


def test_close_position_holding_bars(state):
    """Closing a position should compute holding_bars from timestamp delta."""
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
        lookback_bars=14,
    )

    pnl = state.close_position("X/USDT|Y/USDT", exit_price_a=110.0, exit_price_b=50.0)
    assert pnl is not None

    closed = state.get_all_closed()
    assert len(closed) == 1
    # Opened and closed nearly instantly → holding_bars should be 1 (minimum)
    assert closed[0]["holding_bars"] >= 1


def test_equity_snapshot_with_per_pair_pnl(state):
    """Equity snapshot should persist per_pair_pnl JSON field."""
    per_pair = {"AAA|BBB": 0.015, "CCC|DDD": -0.005}
    state.snapshot_equity(
        total_equity_pct=0.05,
        open_positions=2,
        realized_pnl_pct=0.03,
        unrealized_pnl_pct=0.02,
        per_pair_pnl=json.dumps(per_pair),
    )

    snapshots = state.get_equity_curve()
    assert len(snapshots) == 1
    assert snapshots[0]["per_pair_pnl"] is not None

    recovered = json.loads(snapshots[0]["per_pair_pnl"])
    assert recovered["AAA|BBB"] == 0.015
    assert recovered["CCC|DDD"] == -0.005


def test_record_tick_signal(state):
    """Tick signals should be insertable and retrievable."""
    state.record_tick_signal(
        pair_label="X/USDT|Y/USDT",
        z_score=-1.75,
        weight_a=0.55,
        weight_b=0.45,
        signal="LONG_SPREAD",
        action="ENTRY",
        price_a=100.0,
        price_b=50.0,
    )

    signals = state.get_tick_signals()
    assert len(signals) == 1
    assert signals[0]["pair_label"] == "X/USDT|Y/USDT"
    assert signals[0]["z_score"] == -1.75
    assert signals[0]["signal"] == "LONG_SPREAD"
    assert signals[0]["action"] == "ENTRY"


def test_tick_signals_filter_by_pair(state):
    """get_tick_signals should filter by pair_label when specified."""
    state.record_tick_signal("A|B", -1.5, 0.5, 0.5, "LONG_SPREAD", "ENTRY", 10, 5)
    state.record_tick_signal("C|D", 2.1, 0.6, 0.4, "SHORT_SPREAD", "SKIP", 20, 10)
    state.record_tick_signal("A|B", -0.3, 0.5, 0.5, "FLAT", "HOLD", 10.1, 5.05)

    all_sigs = state.get_tick_signals()
    assert len(all_sigs) == 3

    ab_sigs = state.get_tick_signals(pair_label="A|B")
    assert len(ab_sigs) == 2
    assert all(s["pair_label"] == "A|B" for s in ab_sigs)


def test_schema_migration_idempotent(state):
    """Calling _migrate_schema multiple times should not crash."""
    state._migrate_schema()
    state._migrate_schema()
    # If we get here without exception, the test passes


def test_get_all_orders(state):
    """get_all_orders should return both OPEN and CLOSED."""
    state.open_position("A|B", "A", "B", "LONG_SPREAD", 10, 5, 0.5, 0.5, -2.0, 14)
    state.open_position("C|D", "C", "D", "SHORT_SPREAD", 20, 10, 0.6, 0.4, 2.0, 7)
    state.close_position("A|B", 11, 5)

    all_orders = state.get_all_orders()
    assert len(all_orders) == 2

    statuses = {o["status"] for o in all_orders}
    assert "OPEN" in statuses
    assert "CLOSED" in statuses


def test_user_commands_lifecycle(state):
    """Writing a command should log it as PENDING. Popping retrieves it and marks it EXECUTED."""
    # Write some commands
    state.write_command("/stop_all")
    state.write_command("/stop", target_pair="BTC/USDT")
    
    # 1. Verify retrieval logic
    commands = state.pop_pending_commands()
    assert len(commands) == 2
    assert commands[0]["command"] == "/stop_all"
    assert commands[0]["target_pair"] is None
    assert commands[1]["command"] == "/stop"
    assert commands[1]["target_pair"] == "BTC/USDT"
    
    # 2. Verify state manipulation logic: A second pop should yield nothing!
    commands_again = state.pop_pending_commands()
    assert len(commands_again) == 0
