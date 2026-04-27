"""Runtime key-value state repository for trader state."""

import json
import sqlite3
from typing import Any


class RuntimeStateRepository:
    """Persist durable runtime flags and JSON values."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def set(self, key: str, value: Any, updated_at: str) -> None:
        """Persist a runtime key as JSON."""
        self.conn.execute(
            """INSERT INTO runtime_state (key, value_json, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value_json=excluded.value_json,
                   updated_at=excluded.updated_at""",
            (key, json.dumps(value), updated_at),
        )
        self.conn.commit()

    def get(self, key: str, default: Any = None) -> Any:
        """Read a runtime key from JSON, returning default when absent or malformed."""
        row = self.conn.execute(
            "SELECT value_json FROM runtime_state WHERE key=?",
            (key,),
        ).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value_json"])
        except json.JSONDecodeError:
            return default
