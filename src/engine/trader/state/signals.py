"""Tick signal repository for trader state."""

import sqlite3
from typing import Any


class TickSignalRepository:
    """Record and read per-tick signal evaluations."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def record(
        self,
        timestamp: str,
        pair_label: str,
        z_score: float,
        weight_a: float,
        weight_b: float,
        signal: str,
        action: str,
        price_a: float,
        price_b: float,
    ) -> None:
        """Record a single signal evaluation from a tick."""
        self.conn.execute(
            """INSERT INTO tick_signals
               (timestamp, pair_label, z_score, weight_a, weight_b, signal, action, price_a, price_b)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                timestamp,
                pair_label,
                z_score,
                weight_a,
                weight_b,
                signal,
                action,
                price_a,
                price_b,
            ),
        )
        self.conn.commit()

    def get(self, pair_label: str | None = None) -> list[dict[str, Any]]:
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
