"""Equity snapshot repository for trader state."""

import sqlite3
from typing import Any


class EquityRepository:
    """Record and read mark-to-market equity snapshots."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def snapshot(
        self,
        timestamp: str,
        total_equity_pct: float,
        open_positions: int,
        realized_pnl_pct: float,
        unrealized_pnl_pct: float,
        notes: str,
        per_pair_pnl: str | None,
    ) -> None:
        """Record a periodic mark-to-market equity snapshot."""
        self.conn.execute(
            """INSERT INTO equity_snapshots
               (timestamp, total_equity_pct, open_positions, realized_pnl_pct,
                unrealized_pnl_pct, notes, per_pair_pnl)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                timestamp,
                total_equity_pct,
                open_positions,
                realized_pnl_pct,
                unrealized_pnl_pct,
                notes,
                per_pair_pnl,
            ),
        )
        self.conn.commit()

    def get_curve(self) -> list[dict[str, Any]]:
        """Return all equity snapshots for charting."""
        rows = self.conn.execute(
            "SELECT * FROM equity_snapshots ORDER BY timestamp"
        ).fetchall()
        return [dict(r) for r in rows]
