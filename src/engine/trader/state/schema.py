"""Current trader SQLite schema."""

import sqlite3


SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS spread_positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pair_label TEXT NOT NULL,
        asset_x TEXT NOT NULL,
        asset_y TEXT NOT NULL,
        side TEXT NOT NULL,
        entry_price_a REAL NOT NULL,
        entry_price_b REAL NOT NULL,
        weight_a REAL NOT NULL,
        weight_b REAL NOT NULL,
        entry_z REAL NOT NULL,
        lookback_bars INTEGER NOT NULL,
        opened_at TEXT NOT NULL,
        closed_at TEXT,
        exit_price_a REAL,
        exit_price_b REAL,
        realized_pnl_pct REAL,
        status TEXT NOT NULL DEFAULT 'OPEN',
        exit_z REAL,
        holding_bars INTEGER,
        close_reason TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS order_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        spread_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        idempotency_key TEXT NOT NULL UNIQUE,
        FOREIGN KEY(spread_id) REFERENCES spread_positions(id)
    );

    CREATE TABLE IF NOT EXISTS leg_fills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        spread_id INTEGER NOT NULL,
        leg_role TEXT NOT NULL,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        target_qty REAL NOT NULL,
        filled_qty REAL NOT NULL DEFAULT 0.0,
        avg_fill_price REAL,
        exchange_order_id TEXT,
        client_order_id TEXT,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(spread_id) REFERENCES spread_positions(id)
    );

    CREATE TABLE IF NOT EXISTS equity_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        total_equity_pct REAL NOT NULL,
        open_positions INTEGER NOT NULL,
        realized_pnl_pct REAL NOT NULL,
        unrealized_pnl_pct REAL NOT NULL,
        notes TEXT,
        per_pair_pnl TEXT
    );

    CREATE TABLE IF NOT EXISTS tick_signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        pair_label TEXT NOT NULL,
        z_score REAL NOT NULL,
        weight_a REAL NOT NULL,
        weight_b REAL NOT NULL,
        signal TEXT NOT NULL,
        action TEXT NOT NULL,
        price_a REAL NOT NULL,
        price_b REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS user_commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        command TEXT NOT NULL,
        target_pair TEXT,
        status TEXT NOT NULL DEFAULT 'PENDING',
        claimed_at TEXT,
        completed_at TEXT,
        error TEXT
    );

    CREATE TABLE IF NOT EXISTS runtime_state (
        key TEXT PRIMARY KEY,
        value_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS reconciliation_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        exchange_snapshot_json TEXT NOT NULL,
        local_open_positions_json TEXT NOT NULL,
        status TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS reconciliation_deltas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        delta_type TEXT NOT NULL,
        symbol TEXT,
        spread_id INTEGER,
        action_taken TEXT,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES reconciliation_runs(id),
        FOREIGN KEY(spread_id) REFERENCES spread_positions(id)
    );
"""


def create_schema(conn: sqlite3.Connection) -> None:
    """Create the current trader schema."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()
