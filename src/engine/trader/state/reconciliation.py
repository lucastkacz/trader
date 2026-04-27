"""Exchange/local reconciliation repositories for trader state."""

import sqlite3
from typing import Any

from src.engine.trader.state.serialization import dumps_json


class ReconciliationRepository:
    """Persist reconciliation runs and deltas."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def start_run(
        self,
        started_at: str,
        exchange_snapshot: dict[str, Any],
        local_open_positions: list[dict[str, Any]],
        status: str,
    ) -> int:
        """Start an exchange/local reconciliation run."""
        cursor = self.conn.execute(
            """INSERT INTO reconciliation_runs
               (started_at, exchange_snapshot_json, local_open_positions_json, status)
               VALUES (?, ?, ?, ?)""",
            (
                started_at,
                dumps_json(exchange_snapshot),
                dumps_json(local_open_positions),
                status,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def finish_run(self, run_id: int, finished_at: str, status: str) -> None:
        """Mark a reconciliation run as finished."""
        self.conn.execute(
            """UPDATE reconciliation_runs
               SET finished_at=?, status=?
               WHERE id=?""",
            (finished_at, status, run_id),
        )
        self.conn.commit()

    def record_delta(
        self,
        run_id: int,
        delta_type: str,
        payload: dict[str, Any],
        created_at: str,
        symbol: str | None = None,
        spread_id: int | None = None,
        action_taken: str | None = None,
    ) -> int:
        """Append one reconciliation delta for a run."""
        cursor = self.conn.execute(
            """INSERT INTO reconciliation_deltas
               (run_id, delta_type, symbol, spread_id, action_taken, payload_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                delta_type,
                symbol,
                spread_id,
                action_taken,
                dumps_json(payload),
                created_at,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_runs(self) -> list[dict[str, Any]]:
        """Return reconciliation runs in creation order."""
        rows = self.conn.execute(
            "SELECT * FROM reconciliation_runs ORDER BY started_at, id"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_deltas(self, run_id: int | None = None) -> list[dict[str, Any]]:
        """Return reconciliation deltas, optionally filtered by run."""
        if run_id is None:
            rows = self.conn.execute(
                "SELECT * FROM reconciliation_deltas ORDER BY created_at, id"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM reconciliation_deltas WHERE run_id=? ORDER BY created_at, id",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]
