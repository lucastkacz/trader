"""Leg target/fill repository for trader state."""

import sqlite3
from typing import Any


class LegRepository:
    """Record and read spread leg target rows."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def record_targets(
        self,
        spread_id: int,
        leg_role: str,
        asset_x: str,
        asset_y: str,
        side: str,
        weight_a: float,
        weight_b: float,
        created_at: str,
    ) -> None:
        """Record two pre-execution leg targets for opening or closing a spread."""
        if (leg_role, side) in {("OPEN", "LONG_SPREAD"), ("CLOSE", "SHORT_SPREAD")}:
            leg_specs = [
                (asset_x, "BUY", abs(weight_a)),
                (asset_y, "SELL", abs(weight_b)),
            ]
        else:
            leg_specs = [
                (asset_x, "SELL", abs(weight_a)),
                (asset_y, "BUY", abs(weight_b)),
            ]

        self.conn.executemany(
            """INSERT INTO leg_fills
               (spread_id, leg_role, symbol, side, target_qty, filled_qty, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 0.0, 'TARGET_RECORDED', ?, ?)""",
            [
                (spread_id, leg_role, symbol, leg_side, target_qty, created_at, created_at)
                for symbol, leg_side, target_qty in leg_specs
            ],
        )

    def get(self, spread_id: int | None = None) -> list[dict[str, Any]]:
        """Return leg target/fill rows, optionally filtered by spread id."""
        if spread_id is None:
            rows = self.conn.execute(
                "SELECT * FROM leg_fills ORDER BY created_at, id"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM leg_fills WHERE spread_id=? ORDER BY created_at, id",
                (spread_id,),
            ).fetchall()
        return [dict(r) for r in rows]
