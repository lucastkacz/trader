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
                lookback_days INTEGER NOT NULL,
                timestamp_open TEXT NOT NULL,
                timestamp_close TEXT,
                exit_price_a REAL,
                exit_price_b REAL,
                pnl_pct REAL,
                status TEXT NOT NULL DEFAULT 'OPEN'
            );

            CREATE TABLE IF NOT EXISTS equity_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                total_equity_pct REAL NOT NULL,
                open_positions INTEGER NOT NULL,
                realized_pnl_pct REAL NOT NULL,
                unrealized_pnl_pct REAL NOT NULL,
                notes TEXT
            );
        """)
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
        lookback_days: int,
    ) -> int:
        """Insert a new ghost order. Returns the row ID."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            """INSERT INTO ghost_orders 
               (pair_label, asset_x, asset_y, side, entry_price_a, entry_price_b,
                weight_a, weight_b, entry_z, lookback_days, timestamp_open, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')""",
            (pair_label, asset_x, asset_y, side, entry_price_a, entry_price_b,
             weight_a, weight_b, entry_z, lookback_days, now),
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
        self.conn.execute(
            """UPDATE ghost_orders 
               SET status='CLOSED', timestamp_close=?, exit_price_a=?, exit_price_b=?, pnl_pct=?
               WHERE id=?""",
            (now, exit_price_a, exit_price_b, pnl, row["id"]),
        )
        self.conn.commit()

        ctx = LogContext(pair=pair_label, signal="EXIT")
        logger.bind(**ctx.model_dump(exclude_none=True)).info(
            f"GHOST EXIT | PnL: {pnl*100:.4f}% | "
            f"Exit A={exit_price_a:.6f} B={exit_price_b:.6f}"
        )
        return pnl

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

    def snapshot_equity(
        self,
        total_equity_pct: float,
        open_positions: int,
        realized_pnl_pct: float,
        unrealized_pnl_pct: float,
        notes: str = "",
    ):
        """Record a periodic mark-to-market equity snapshot."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO equity_snapshots
               (timestamp, total_equity_pct, open_positions, realized_pnl_pct, unrealized_pnl_pct, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (now, total_equity_pct, open_positions, realized_pnl_pct, unrealized_pnl_pct, notes),
        )
        self.conn.commit()

    def get_equity_curve(self) -> List[Dict[str, Any]]:
        """Returns all equity snapshots for charting."""
        rows = self.conn.execute(
            "SELECT * FROM equity_snapshots ORDER BY timestamp"
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        """Cleanly close the database connection."""
        self.conn.close()
