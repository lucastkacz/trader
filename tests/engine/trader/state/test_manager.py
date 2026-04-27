"""
Tests for TradeStateManager.
Uses in-memory SQLite to avoid filesystem side effects.
"""

import json
import pytest
from src.engine.trader.state_manager import TradeStateManager


@pytest.fixture
def state():
    """Create a fresh in-memory state manager for each test."""
    mgr = TradeStateManager(db_path=":memory:")
    yield mgr
    mgr.close()


def test_open_and_retrieve_position(state):
    """Opening a position should be retrievable."""
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


def test_state_schema_uses_spread_positions(state):
    """The canonical trader schema should not recreate legacy position tables."""
    rows = state.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = {row["name"] for row in rows}

    assert "spread_positions" in table_names
    assert "order_events" in table_names
    assert "leg_fills" in table_names
    assert "reconciliation_runs" in table_names
    assert "reconciliation_deltas" in table_names
    assert "ghost_orders" not in table_names


def test_runtime_state_defaults_to_unpaused(state):
    """Runtime pause state should default to running."""
    assert state.is_system_paused() is False


def test_runtime_state_persists_json_values(state):
    """Runtime state should store JSON values by stable key."""
    state.set_runtime_state("engine_version", {"git_sha": "abc123"})
    state.set_system_paused(True)

    assert state.get_runtime_state("engine_version") == {"git_sha": "abc123"}
    assert state.is_system_paused() is True

    state.set_system_paused(False)
    assert state.is_system_paused() is False


def test_file_backed_sqlite_pragmas(tmp_path):
    """File-backed databases should use production durability and contention settings."""
    db_path = tmp_path / "trader.db"
    mgr = TradeStateManager(db_path=str(db_path))
    try:
        journal_mode = mgr.conn.execute("PRAGMA journal_mode;").fetchone()[0]
        synchronous = mgr.conn.execute("PRAGMA synchronous;").fetchone()[0]
        foreign_keys = mgr.conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        busy_timeout = mgr.conn.execute("PRAGMA busy_timeout;").fetchone()[0]
    finally:
        mgr.close()

    assert journal_mode.lower() == "wal"
    assert synchronous == 2
    assert foreign_keys == 1
    assert busy_timeout == 5000


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


def test_position_lifecycle_writes_order_events(state):
    """Opening and closing a spread should append auditable order events."""
    spread_id = state.open_position(
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
    state.close_position(
        "X/USDT|Y/USDT",
        exit_price_a=110.0,
        exit_price_b=50.0,
        exit_z=0.1,
        close_reason="SIGNAL_EXIT",
    )

    events = state.get_order_events(spread_id=spread_id)
    assert [event["event_type"] for event in events] == ["SIGNAL_ENTRY", "SIGNAL_EXIT"]
    assert all(event["spread_id"] == spread_id for event in events)
    assert all(event["idempotency_key"] for event in events)

    entry_payload = json.loads(events[0]["payload_json"])
    close_payload = json.loads(events[1]["payload_json"])

    assert entry_payload["pair_label"] == "X/USDT|Y/USDT"
    assert entry_payload["side"] == "LONG_SPREAD"
    assert close_payload["realized_pnl_pct"] == pytest.approx(0.05)
    assert close_payload["holding_bars"] >= 1


def test_open_position_records_long_spread_leg_targets(state):
    """LONG_SPREAD should target long asset X and short asset Y."""
    spread_id = state.open_position(
        pair_label="X/USDT|Y/USDT",
        asset_x="X/USDT",
        asset_y="Y/USDT",
        side="LONG_SPREAD",
        entry_price_a=100.0,
        entry_price_b=50.0,
        weight_a=0.6,
        weight_b=0.4,
        entry_z=-2.0,
        lookback_bars=21,
    )

    legs = state.get_leg_fills(spread_id=spread_id)
    assert len(legs) == 2
    assert [leg["leg_role"] for leg in legs] == ["OPEN", "OPEN"]
    assert [(leg["symbol"], leg["side"]) for leg in legs] == [
        ("X/USDT", "BUY"),
        ("Y/USDT", "SELL"),
    ]
    assert [leg["target_qty"] for leg in legs] == [0.6, 0.4]
    assert [leg["filled_qty"] for leg in legs] == [0.0, 0.0]
    assert all(leg["status"] == "TARGET_RECORDED" for leg in legs)
    assert all(leg["exchange_order_id"] is None for leg in legs)


def test_open_position_records_short_spread_leg_targets(state):
    """SHORT_SPREAD should target short asset X and long asset Y."""
    spread_id = state.open_position(
        pair_label="X/USDT|Y/USDT",
        asset_x="X/USDT",
        asset_y="Y/USDT",
        side="SHORT_SPREAD",
        entry_price_a=100.0,
        entry_price_b=50.0,
        weight_a=0.6,
        weight_b=0.4,
        entry_z=2.0,
        lookback_bars=21,
    )

    legs = state.get_leg_fills(spread_id=spread_id)
    assert [leg["leg_role"] for leg in legs] == ["OPEN", "OPEN"]
    assert [(leg["symbol"], leg["side"]) for leg in legs] == [
        ("X/USDT", "SELL"),
        ("Y/USDT", "BUY"),
    ]


def test_close_position_records_close_leg_targets(state):
    """Closing a spread should add reverse-side close targets without mutating open targets."""
    spread_id = state.open_position(
        pair_label="X/USDT|Y/USDT",
        asset_x="X/USDT",
        asset_y="Y/USDT",
        side="LONG_SPREAD",
        entry_price_a=100.0,
        entry_price_b=50.0,
        weight_a=0.6,
        weight_b=0.4,
        entry_z=-2.0,
        lookback_bars=21,
    )

    state.close_position("X/USDT|Y/USDT", 101.0, 49.0)

    legs = state.get_leg_fills(spread_id=spread_id)
    assert len(legs) == 4
    assert [(leg["leg_role"], leg["symbol"], leg["side"]) for leg in legs] == [
        ("OPEN", "X/USDT", "BUY"),
        ("OPEN", "Y/USDT", "SELL"),
        ("CLOSE", "X/USDT", "SELL"),
        ("CLOSE", "Y/USDT", "BUY"),
    ]
    assert [leg["status"] for leg in legs] == ["TARGET_RECORDED"] * 4


def test_close_position_records_short_spread_close_leg_targets(state):
    """Closing a short spread should buy back asset X and sell asset Y."""
    spread_id = state.open_position(
        pair_label="X/USDT|Y/USDT",
        asset_x="X/USDT",
        asset_y="Y/USDT",
        side="SHORT_SPREAD",
        entry_price_a=100.0,
        entry_price_b=50.0,
        weight_a=0.6,
        weight_b=0.4,
        entry_z=2.0,
        lookback_bars=21,
    )

    state.close_position("X/USDT|Y/USDT", 99.0, 51.0)

    close_legs = [
        leg for leg in state.get_leg_fills(spread_id=spread_id)
        if leg["leg_role"] == "CLOSE"
    ]
    assert [(leg["symbol"], leg["side"]) for leg in close_legs] == [
        ("X/USDT", "BUY"),
        ("Y/USDT", "SELL"),
    ]


def test_leg_fills_require_existing_spread(state):
    """Foreign keys should prevent orphan leg targets."""
    with pytest.raises(Exception):
        state._record_leg_targets(
            spread_id=999,
            leg_role="OPEN",
            asset_x="X/USDT",
            asset_y="Y/USDT",
            side="LONG_SPREAD",
            weight_a=0.6,
            weight_b=0.4,
            created_at="2026-01-01T00:00:00+00:00",
        )


def test_order_events_require_existing_spread(state):
    """Foreign keys should prevent orphan order events."""
    with pytest.raises(Exception):
        state._record_order_event(
            spread_id=999,
            event_type="SIGNAL_ENTRY",
            payload={"pair_label": "MISSING"},
            created_at="2026-01-01T00:00:00+00:00",
            idempotency_key="missing-spread",
        )


def test_close_reason_is_persisted(state):
    """Close reason should be stored on the projection and event ledger."""
    spread_id = state.open_position(
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

    state.close_position("X/USDT|Y/USDT", 90.0, 55.0, close_reason="FORCE_CLOSE_REQUESTED")

    closed = state.get_all_closed()
    events = state.get_order_events(spread_id=spread_id)

    assert closed[0]["close_reason"] == "FORCE_CLOSE_REQUESTED"
    assert events[-1]["event_type"] == "FORCE_CLOSE_REQUESTED"


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
    """Commands should move through explicit claimed and terminal statuses."""
    state.write_command("/stop_all")
    state.write_command("/stop", target_pair="BTC/USDT")

    pending = state.get_commands()
    assert [cmd["status"] for cmd in pending] == ["PENDING", "PENDING"]

    commands = state.claim_pending_commands()
    assert len(commands) == 2
    assert commands[0]["command"] == "/stop_all"
    assert commands[0]["target_pair"] is None
    assert commands[1]["command"] == "/stop"
    assert commands[1]["target_pair"] == "BTC/USDT"

    claimed = state.get_commands()
    assert [cmd["status"] for cmd in claimed] == ["CLAIMED", "CLAIMED"]
    assert all(cmd["claimed_at"] is not None for cmd in claimed)

    state.mark_command_executed(commands[0]["id"])
    state.mark_command_failed(commands[1]["id"], "exchange unavailable")

    completed = state.get_commands()
    assert [cmd["status"] for cmd in completed] == ["EXECUTED", "FAILED"]
    assert completed[0]["completed_at"] is not None
    assert completed[1]["error"] == "exchange unavailable"

    commands_again = state.claim_pending_commands()
    assert len(commands_again) == 0


def test_user_command_ignored_status(state):
    """Ignored commands should preserve their reason for auditability."""
    state.write_command("/unknown")

    commands = state.claim_pending_commands()
    state.mark_command_ignored(commands[0]["id"], "unknown command")

    rows = state.get_commands()
    assert rows[0]["status"] == "IGNORED"
    assert rows[0]["error"] == "unknown command"


def test_reconciliation_run_lifecycle(state):
    """Reconciliation runs should persist snapshots and terminal status."""
    state.open_position("X/USDT|Y/USDT", "X/USDT", "Y/USDT", "LONG_SPREAD", 100, 50, 0.6, 0.4, -2.0, 21)
    local_positions = state.get_open_positions()

    run_id = state.start_reconciliation_run(
        exchange_snapshot={"positions": [{"symbol": "X/USDT", "qty": 0.6}]},
        local_open_positions=local_positions,
    )
    state.finish_reconciliation_run(run_id, status="MATCHED")

    runs = state.get_reconciliation_runs()
    assert len(runs) == 1
    assert runs[0]["id"] == run_id
    assert runs[0]["status"] == "MATCHED"
    assert runs[0]["finished_at"] is not None

    exchange_snapshot = json.loads(runs[0]["exchange_snapshot_json"])
    local_snapshot = json.loads(runs[0]["local_open_positions_json"])
    assert exchange_snapshot["positions"][0]["symbol"] == "X/USDT"
    assert local_snapshot[0]["pair_label"] == "X/USDT|Y/USDT"


def test_reconciliation_deltas_attach_to_run_and_spread(state):
    """Reconciliation deltas should be queryable by run."""
    spread_id = state.open_position("X|Y", "X", "Y", "LONG_SPREAD", 100, 50, 0.5, 0.5, -2.0, 21)
    run_id = state.start_reconciliation_run(
        exchange_snapshot={"positions": []},
        local_open_positions=state.get_open_positions(),
    )

    delta_id = state.record_reconciliation_delta(
        run_id=run_id,
        delta_type="LOCAL_ONLY_POSITION",
        symbol="X",
        spread_id=spread_id,
        action_taken="NO_ACTION",
        payload={"reason": "paper target only"},
    )

    deltas = state.get_reconciliation_deltas(run_id=run_id)
    assert len(deltas) == 1
    assert deltas[0]["id"] == delta_id
    assert deltas[0]["delta_type"] == "LOCAL_ONLY_POSITION"
    assert deltas[0]["spread_id"] == spread_id
    assert json.loads(deltas[0]["payload_json"]) == {"reason": "paper target only"}


def test_reconciliation_deltas_require_existing_run(state):
    """Foreign keys should prevent deltas without a run."""
    with pytest.raises(Exception):
        state.record_reconciliation_delta(
            run_id=999,
            delta_type="EXCHANGE_ONLY_POSITION",
            symbol="X",
            payload={"qty": 1.0},
        )
