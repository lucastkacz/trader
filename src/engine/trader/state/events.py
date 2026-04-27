"""Order-event ledger repository for trader state."""

import sqlite3
from typing import Any

from src.engine.trader.state.serialization import dumps_json


class EventRepository:
    """Append and read immutable order events."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def append(
        self,
        spread_id: int,
        event_type: str,
        payload: dict[str, Any],
        created_at: str,
        idempotency_key: str,
    ) -> None:
        """Append an order event inside the caller's transaction."""
        self.conn.execute(
            """INSERT INTO order_events
               (spread_id, event_type, payload_json, created_at, idempotency_key)
               VALUES (?, ?, ?, ?, ?)""",
            (spread_id, event_type, dumps_json(payload), created_at, idempotency_key),
        )

    def get(self, spread_id: int | None = None) -> list[dict[str, Any]]:
        """Return append-only order events, optionally filtered by spread id."""
        if spread_id is None:
            rows = self.conn.execute(
                "SELECT * FROM order_events ORDER BY created_at, id"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM order_events WHERE spread_id=? ORDER BY created_at, id",
                (spread_id,),
            ).fetchall()
        return [dict(r) for r in rows]
