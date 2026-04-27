"""Spread-position projection repository for trader state."""

import sqlite3
from typing import Any


class PositionRepository:
    """Read and mutate spread position projection rows."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert_open(
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
        opened_at: str,
    ) -> int:
        """Insert a new open spread position."""
        cursor = self.conn.execute(
            """INSERT INTO spread_positions
               (pair_label, asset_x, asset_y, side, entry_price_a, entry_price_b,
                weight_a, weight_b, entry_z, lookback_bars, opened_at, status,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)""",
            (
                pair_label,
                asset_x,
                asset_y,
                side,
                entry_price_a,
                entry_price_b,
                weight_a,
                weight_b,
                entry_z,
                lookback_bars,
                opened_at,
                opened_at,
                opened_at,
            ),
        )
        return cursor.lastrowid

    def close(
        self,
        spread_id: int,
        closed_at: str,
        exit_price_a: float,
        exit_price_b: float,
        realized_pnl_pct: float,
        exit_z: float | None,
        holding_bars: int,
        close_reason: str,
    ) -> None:
        """Mark an open spread position as closed."""
        self.conn.execute(
            """UPDATE spread_positions
               SET status='CLOSED', closed_at=?, exit_price_a=?, exit_price_b=?,
                   realized_pnl_pct=?, exit_z=?, holding_bars=?, close_reason=?, updated_at=?
               WHERE id=?""",
            (
                closed_at,
                exit_price_a,
                exit_price_b,
                realized_pnl_pct,
                exit_z,
                holding_bars,
                close_reason,
                closed_at,
                spread_id,
            ),
        )

    def get_open(self) -> list[dict[str, Any]]:
        """Return all currently open positions."""
        rows = self.conn.execute(
            "SELECT * FROM spread_positions WHERE status='OPEN'"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_open_for_pair_row(self, pair_label: str) -> sqlite3.Row | None:
        """Return the open row for a pair, if any."""
        return self.conn.execute(
            "SELECT * FROM spread_positions WHERE pair_label=? AND status='OPEN' LIMIT 1",
            (pair_label,),
        ).fetchone()

    def get_open_for_pair(self, pair_label: str) -> dict[str, Any] | None:
        """Return the open position for a pair, if any."""
        row = self.get_open_for_pair_row(pair_label)
        return dict(row) if row else None

    def get_closed(self) -> list[dict[str, Any]]:
        """Return all closed positions for the trade log."""
        rows = self.conn.execute(
            "SELECT * FROM spread_positions WHERE status='CLOSED' ORDER BY closed_at"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all(self) -> list[dict[str, Any]]:
        """Return all spread positions."""
        rows = self.conn.execute(
            "SELECT * FROM spread_positions ORDER BY opened_at"
        ).fetchall()
        return [dict(r) for r in rows]
