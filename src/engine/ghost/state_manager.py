"""
Ghost Trading State Manager
============================
SQLite-backed persistence layer for Epoch 3 paper trading.
Manages ghost orders and equity snapshots with WAL mode for crash safety.
"""

import os
import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from src.core.logger import logger, LogContext
from src.core.config import settings


class GhostStateManager:
    """
    ACID-compliant SQLite engine for ghost trade lifecycle management.
    WAL mode ensures no corruption on process kill mid-write.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.ghost_db_path
        db_dir = os.path.dirname(self.db_path)
        if db_dir:  # Skip for in-memory SQLite (":memory:")
            os.makedirs(db_dir, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA busy_timeout=5000;")
        self._create_tables()
        self._migrate_schema()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS ghost_orders (
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
                timestamp_open TEXT NOT NULL,
                timestamp_close TEXT,
                exit_price_a REAL,
                exit_price_b REAL,
                pnl_pct REAL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                exit_z REAL,
                holding_bars INTEGER
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
                status TEXT NOT NULL DEFAULT 'PENDING'
            );
        """)
        self.conn.commit()

    def _migrate_schema(self):
        """
        Backward-compatible schema migration for existing databases.
        ALTER TABLE ADD COLUMN is idempotent — we catch 'duplicate column' errors.
        This ensures pre-reporting DBs (turbo, production) upgrade automatically.
        """
        migrations = [
            "ALTER TABLE ghost_orders ADD COLUMN exit_z REAL",
            "ALTER TABLE ghost_orders ADD COLUMN holding_bars INTEGER",
            "ALTER TABLE equity_snapshots ADD COLUMN per_pair_pnl TEXT",
            # We don't need ALTER TABLE for user_commands because we added it directly to CREATE TABLE,
            # but if it didn't exist in older DBs, the next line creates it:
            "CREATE TABLE IF NOT EXISTS user_commands (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, command TEXT NOT NULL, target_pair TEXT, status TEXT NOT NULL DEFAULT 'PENDING')"
        ]
        for sql in migrations:
            try:
                self.conn.execute(sql)
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise
        self.conn.commit()

    def open_position(
        self,
        pair_label: str,
        asset_x: str,
        asset_y: str,
        side: str,
        entry_price_a: float,
        entry_price_b: float,
        weight_a: float,
        weight_b: float,
        entry_z: float,
        lookback_bars: int,
    ) -> int:
        """Insert a new ghost order. Returns the row ID."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            """INSERT INTO ghost_orders 
               (pair_label, asset_x, asset_y, side, entry_price_a, entry_price_b,
                weight_a, weight_b, entry_z, lookback_bars, timestamp_open, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')""",
            (pair_label, asset_x, asset_y, side, entry_price_a, entry_price_b,
             weight_a, weight_b, entry_z, lookback_bars, now),
        )
        self.conn.commit()

        ctx = LogContext(pair=pair_label, signal=side)
        logger.bind(**ctx.model_dump(exclude_none=True)).info(
            f"GHOST ENTRY | {side} @ A={entry_price_a:.6f} B={entry_price_b:.6f} | "
            f"Weights: A={weight_a:.4f} B={weight_b:.4f} | Z={entry_z:.4f}"
        )
        return cursor.lastrowid

    def close_position(
        self,
        pair_label: str,
        exit_price_a: float,
        exit_price_b: float,
        exit_z: Optional[float] = None,
    ) -> Optional[float]:
        """
        Close the open ghost order for a pair. Calculates realized PnL.
        Returns the PnL percentage, or None if no open position found.
        """
        row = self.conn.execute(
            "SELECT * FROM ghost_orders WHERE pair_label=? AND status='OPEN' LIMIT 1",
            (pair_label,),
        ).fetchone()

        if row is None:
            return None

        # Calculate PnL using the same volatility-parity-weighted logic as the backtest
        ret_a = (exit_price_a - row["entry_price_a"]) / row["entry_price_a"]
        ret_b = (exit_price_b - row["entry_price_b"]) / row["entry_price_b"]

        if row["side"] == "LONG_SPREAD":
            pnl = row["weight_a"] * ret_a - row["weight_b"] * ret_b
        else:  # SHORT_SPREAD
            pnl = -row["weight_a"] * ret_a + row["weight_b"] * ret_b

        now = datetime.now(timezone.utc).isoformat()

        # Compute holding_bars from timestamp delta
        holding_bars = self._compute_holding_bars(row["timestamp_open"], now)

        self.conn.execute(
            """UPDATE ghost_orders 
               SET status='CLOSED', timestamp_close=?, exit_price_a=?, exit_price_b=?,
                   pnl_pct=?, exit_z=?, holding_bars=?
               WHERE id=?""",
            (now, exit_price_a, exit_price_b, pnl, exit_z, holding_bars, row["id"]),
        )
        self.conn.commit()

        ctx = LogContext(pair=pair_label, signal="EXIT")
        logger.bind(**ctx.model_dump(exclude_none=True)).info(
            f"GHOST EXIT | PnL: {pnl*100:.4f}% | "
            f"Exit A={exit_price_a:.6f} B={exit_price_b:.6f} | "
            f"Z={exit_z:.4f} | Bars={holding_bars}"
            if exit_z is not None else
            f"GHOST EXIT | PnL: {pnl*100:.4f}% | "
            f"Exit A={exit_price_a:.6f} B={exit_price_b:.6f}"
        )
        return pnl

    @staticmethod
    def _compute_holding_bars(open_ts: str, close_ts: str) -> int:
        """
        Compute holding duration in 4H bars from ISO timestamps.
        Uses actual time delta, so it works for any candle interval.
        Minimum 1 bar (even if closed within the same tick).
        """
        try:
            # Handle both timezone-aware and naive timestamps
            t_open = datetime.fromisoformat(open_ts.replace("Z", "+00:00"))
            t_close = datetime.fromisoformat(close_ts.replace("Z", "+00:00"))
            delta_hours = (t_close - t_open).total_seconds() / 3600.0
            bars = max(1, int(round(delta_hours / 4.0)))
            return bars
        except (ValueError, TypeError):
            return 1

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Returns all currently open ghost positions."""
        rows = self.conn.execute(
            "SELECT * FROM ghost_orders WHERE status='OPEN'"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_position_for_pair(self, pair_label: str) -> Optional[Dict[str, Any]]:
        """Returns the open position for a specific pair, if any."""
        row = self.conn.execute(
            "SELECT * FROM ghost_orders WHERE pair_label=? AND status='OPEN' LIMIT 1",
            (pair_label,),
        ).fetchone()
        return dict(row) if row else None

    def get_all_closed(self) -> List[Dict[str, Any]]:
        """Returns all closed ghost orders for the trade log."""
        rows = self.conn.execute(
            "SELECT * FROM ghost_orders WHERE status='CLOSED' ORDER BY timestamp_close"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_orders(self) -> List[Dict[str, Any]]:
        """Returns ALL ghost orders (OPEN + CLOSED) for the report engine."""
        rows = self.conn.execute(
            "SELECT * FROM ghost_orders ORDER BY timestamp_open"
        ).fetchall()
        return [dict(r) for r in rows]

    def snapshot_equity(
        self,
        total_equity_pct: float,
        open_positions: int,
        realized_pnl_pct: float,
        unrealized_pnl_pct: float,
        notes: str = "",
        per_pair_pnl: Optional[str] = None,
    ):
        """Record a periodic mark-to-market equity snapshot."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO equity_snapshots
               (timestamp, total_equity_pct, open_positions, realized_pnl_pct,
                unrealized_pnl_pct, notes, per_pair_pnl)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (now, total_equity_pct, open_positions, realized_pnl_pct,
             unrealized_pnl_pct, notes, per_pair_pnl),
        )
        self.conn.commit()

    def get_equity_curve(self) -> List[Dict[str, Any]]:
        """Returns all equity snapshots for charting."""
        rows = self.conn.execute(
            "SELECT * FROM equity_snapshots ORDER BY timestamp"
        ).fetchall()
        return [dict(r) for r in rows]

    def record_tick_signal(
        self,
        pair_label: str,
        z_score: float,
        weight_a: float,
        weight_b: float,
        signal: str,
        action: str,
        price_a: float,
        price_b: float,
    ):
        """Record a single signal evaluation from a tick. Called for EVERY pair on EVERY tick."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO tick_signals
               (timestamp, pair_label, z_score, weight_a, weight_b, signal, action, price_a, price_b)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (now, pair_label, z_score, weight_a, weight_b, signal, action, price_a, price_b),
        )
        self.conn.commit()

    def get_tick_signals(self, pair_label: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve tick signals, optionally filtered by pair."""
        if pair_label:
            rows = self.conn.execute(
                "SELECT * FROM tick_signals WHERE pair_label=? ORDER BY timestamp",
                (pair_label,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM tick_signals ORDER BY timestamp"
            ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        """Cleanly close the database connection."""
        self.conn.close()

    # ─── Commands Interface ──────────────────────────────────────────

    def write_command(self, command: str, target_pair: Optional[str] = None):
        """Write a new pending command from the UI."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO user_commands (timestamp, command, target_pair) VALUES (?, ?, ?)",
            (now, command, target_pair)
        )
        self.conn.commit()

    def pop_pending_commands(self) -> List[Dict[str, Any]]:
        """Fetch all pending commands and mark them as executed."""
        rows = self.conn.execute(
            "SELECT * FROM user_commands WHERE status='PENDING' ORDER BY timestamp"
        ).fetchall()
        
        commands = [dict(r) for r in rows]
        if commands:
            ids = tuple(c['id'] for c in commands)
            placeholders = ",".join("?" for _ in ids)
            self.conn.execute(
                f"UPDATE user_commands SET status='EXECUTED' WHERE id IN ({placeholders})",
                ids
            )
            self.conn.commit()
            
        return commands
