"""User command lifecycle repository for trader state."""

import sqlite3
from typing import Any


class CommandRepository:
    """Write, claim, and complete user commands."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def write(self, timestamp: str, command: str, target_pair: str | None = None) -> None:
        """Write a new pending command from the UI."""
        self.conn.execute(
            "INSERT INTO user_commands (timestamp, command, target_pair) VALUES (?, ?, ?)",
            (timestamp, command, target_pair),
        )
        self.conn.commit()

    def claim_pending(self, claimed_at: str) -> list[dict[str, Any]]:
        """Claim all pending commands so execution can safely mark the final outcome."""
        with self.conn:
            rows = self.conn.execute(
                "SELECT * FROM user_commands WHERE status='PENDING' ORDER BY timestamp"
            ).fetchall()

            commands = [dict(r) for r in rows]
            if commands:
                ids = tuple(c["id"] for c in commands)
                placeholders = ",".join("?" for _ in ids)
                self.conn.execute(
                    f"""UPDATE user_commands
                        SET status='CLAIMED', claimed_at=?
                        WHERE id IN ({placeholders})""",
                    (claimed_at, *ids),
                )

        return commands

    def mark_terminal(
        self,
        command_id: int,
        status: str,
        completed_at: str,
        error: str | None = None,
    ) -> None:
        """Mark a claimed command as terminal."""
        self.conn.execute(
            """UPDATE user_commands
               SET status=?, completed_at=?, error=?
               WHERE id=?""",
            (status, completed_at, error, command_id),
        )
        self.conn.commit()

    def get_all(self) -> list[dict[str, Any]]:
        """Return all user commands for tests and diagnostics."""
        rows = self.conn.execute(
            "SELECT * FROM user_commands ORDER BY timestamp"
        ).fetchall()
        return [dict(r) for r in rows]
