"""Current-schema migration hooks for trader state."""

import sqlite3


def migrate_schema(conn: sqlite3.Connection) -> None:
    """
    Current-schema hook for future explicit migrations.
    Legacy pre-trader schemas are intentionally not preserved.
    """
    conn.commit()
