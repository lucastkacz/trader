"""
Trade State Manager
====================
SQLite-backed persistence layer for the trader engine.
Manages orders and equity snapshots with WAL mode for crash safety.
"""

import os
import json
import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from src.core.logger import logger, LogContext


class TradeStateManager:
    """
    ACID-compliant SQLite engine for trade lifecycle management.
    WAL mode ensures no corruption on process kill mid-write.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        db_dir = os.path.dirname(self.db_path)
        if db_dir:  # Skip for in-memory SQLite (":memory:")
            os.makedirs(db_dir, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=FULL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")
        self.conn.execute("PRAGMA busy_timeout=5000;")
        self._create_tables()
        self._migrate_schema()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS spread_positions (
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
                lookback_bars INTEGER NOT NULL,
                opened_at TEXT NOT NULL,
                closed_at TEXT,
                exit_price_a REAL,
                exit_price_b REAL,
                realized_pnl_pct REAL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                exit_z REAL,
                holding_bars INTEGER,
                close_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS order_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spread_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                FOREIGN KEY(spread_id) REFERENCES spread_positions(id)
            );

            CREATE TABLE IF NOT EXISTS leg_fills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spread_id INTEGER NOT NULL,
                leg_role TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                target_qty REAL NOT NULL,
                filled_qty REAL NOT NULL DEFAULT 0.0,
                avg_fill_price REAL,
                exchange_order_id TEXT,
                client_order_id TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(spread_id) REFERENCES spread_positions(id)
            );

            CREATE TABLE IF NOT EXISTS equity_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                total_equity_pct REAL NOT NULL,
                open_positions INTEGER NOT NULL,
                realized_pnl_pct REAL NOT NULL,
                unrealized_pnl_pct REAL NOT NULL,
                notes TEXT,
                per_pair_pnl TEXT
            );

            CREATE TABLE IF NOT EXISTS tick_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                pair_label TEXT NOT NULL,
                z_score REAL NOT NULL,
                weight_a REAL NOT NULL,
                weight_b REAL NOT NULL,
                signal TEXT NOT NULL,
                action TEXT NOT NULL,
                price_a REAL NOT NULL,
                price_b REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                command TEXT NOT NULL,
                target_pair TEXT,
                status TEXT NOT NULL DEFAULT 'PENDING',
                claimed_at TEXT,
                completed_at TEXT,
                error TEXT
            );

            CREATE TABLE IF NOT EXISTS runtime_state (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reconciliation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                exchange_snapshot_json TEXT NOT NULL,
                local_open_positions_json TEXT NOT NULL,
                status TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reconciliation_deltas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                delta_type TEXT NOT NULL,
                symbol TEXT,
                spread_id INTEGER,
                action_taken TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES reconciliation_runs(id),
                FOREIGN KEY(spread_id) REFERENCES spread_positions(id)
            );
        """)
        self.conn.commit()

    def _migrate_schema(self):
        """
        Current-schema hook for future explicit migrations.
        Legacy pre-trader schemas are intentionally not preserved.
        """
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
        lookback_bars: int,
    ) -> int:
        """Insert a new spread position. Returns the row ID."""
        now = datetime.now(timezone.utc).isoformat()
        with self.conn:
            cursor = self.conn.execute(
                """INSERT INTO spread_positions 
                   (pair_label, asset_x, asset_y, side, entry_price_a, entry_price_b,
                    weight_a, weight_b, entry_z, lookback_bars, opened_at, status,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)""",
                (pair_label, asset_x, asset_y, side, entry_price_a, entry_price_b,
                 weight_a, weight_b, entry_z, lookback_bars, now, now, now),
            )
            spread_id = cursor.lastrowid
            self._record_order_event(
                spread_id=spread_id,
                event_type="SIGNAL_ENTRY",
                payload={
                    "pair_label": pair_label,
                    "asset_x": asset_x,
                    "asset_y": asset_y,
                    "side": side,
                    "entry_price_a": entry_price_a,
                    "entry_price_b": entry_price_b,
                    "weight_a": weight_a,
                    "weight_b": weight_b,
                    "entry_z": entry_z,
                    "lookback_bars": lookback_bars,
                },
                created_at=now,
                idempotency_key=f"spread:{spread_id}:SIGNAL_ENTRY:{now}",
            )
            self._record_leg_targets(
                spread_id=spread_id,
                leg_role="OPEN",
                asset_x=asset_x,
                asset_y=asset_y,
                side=side,
                weight_a=weight_a,
                weight_b=weight_b,
                created_at=now,
            )

        ctx = LogContext(pair=pair_label, signal=side)
        logger.bind(**ctx.model_dump(exclude_none=True)).info(
            f"ENTRY | {side} @ A={entry_price_a:.6f} B={entry_price_b:.6f} | "
            f"Weights: A={weight_a:.4f} B={weight_b:.4f} | Z={entry_z:.4f}"
        )
        return spread_id

    def close_position(
        self,
        pair_label: str,
        exit_price_a: float,
        exit_price_b: float,
        exit_z: Optional[float] = None,
        close_reason: str = "SIGNAL_EXIT",
    ) -> Optional[float]:
        """
        Close the open order for a pair. Calculates realized PnL.
        Returns the PnL percentage, or None if no open position found.
        """
        row = self.conn.execute(
            "SELECT * FROM spread_positions WHERE pair_label=? AND status='OPEN' LIMIT 1",
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

        # Compute holding_bars from timestamp delta
        holding_bars = self._compute_holding_bars(row["opened_at"], now)

        with self.conn:
            self.conn.execute(
                """UPDATE spread_positions 
                   SET status='CLOSED', closed_at=?, exit_price_a=?, exit_price_b=?,
                       realized_pnl_pct=?, exit_z=?, holding_bars=?, close_reason=?, updated_at=?
                   WHERE id=?""",
                (now, exit_price_a, exit_price_b, pnl, exit_z, holding_bars,
                 close_reason, now, row["id"]),
            )
            self._record_order_event(
                spread_id=row["id"],
                event_type=close_reason,
                payload={
                    "pair_label": pair_label,
                    "exit_price_a": exit_price_a,
                    "exit_price_b": exit_price_b,
                    "exit_z": exit_z,
                    "realized_pnl_pct": pnl,
                    "holding_bars": holding_bars,
                },
                created_at=now,
                idempotency_key=f"spread:{row['id']}:{close_reason}:{now}",
            )
            self._record_leg_targets(
                spread_id=row["id"],
                leg_role="CLOSE",
                asset_x=row["asset_x"],
                asset_y=row["asset_y"],
                side=row["side"],
                weight_a=row["weight_a"],
                weight_b=row["weight_b"],
                created_at=now,
            )

        ctx = LogContext(pair=pair_label, signal="EXIT")
        logger.bind(**ctx.model_dump(exclude_none=True)).info(
            f"EXIT | PnL: {pnl*100:.4f}% | "
            f"Exit A={exit_price_a:.6f} B={exit_price_b:.6f} | "
            f"Z={exit_z:.4f} | Bars={holding_bars}"
            if exit_z is not None else
            f"EXIT | PnL: {pnl*100:.4f}% | "
            f"Exit A={exit_price_a:.6f} B={exit_price_b:.6f}"
        )
        return pnl

    @staticmethod
    def _compute_holding_bars(open_ts: str, close_ts: str) -> int:
        """
        Compute holding duration in 4H bars from ISO timestamps.
        Uses actual time delta, so it works for any candle interval.
        Minimum 1 bar (even if closed within the same tick).
        """
        try:
            # Handle both timezone-aware and naive timestamps
            t_open = datetime.fromisoformat(open_ts.replace("Z", "+00:00"))
            t_close = datetime.fromisoformat(close_ts.replace("Z", "+00:00"))
            delta_hours = (t_close - t_open).total_seconds() / 3600.0
            bars = max(1, int(round(delta_hours / 4.0)))
            return bars
        except (ValueError, TypeError):
            return 1

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Returns all currently open positions."""
        rows = self.conn.execute(
            "SELECT * FROM spread_positions WHERE status='OPEN'"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_position_for_pair(self, pair_label: str) -> Optional[Dict[str, Any]]:
        """Returns the open position for a specific pair, if any."""
        row = self.conn.execute(
            "SELECT * FROM spread_positions WHERE pair_label=? AND status='OPEN' LIMIT 1",
            (pair_label,),
        ).fetchone()
        return dict(row) if row else None

    def get_all_closed(self) -> List[Dict[str, Any]]:
        """Returns all closed positions for the trade log."""
        rows = self.conn.execute(
            "SELECT * FROM spread_positions WHERE status='CLOSED' ORDER BY closed_at"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_orders(self) -> List[Dict[str, Any]]:
        """Returns ALL spread positions (OPEN + CLOSED) for the report engine."""
        rows = self.conn.execute(
            "SELECT * FROM spread_positions ORDER BY opened_at"
        ).fetchall()
        return [dict(r) for r in rows]

    def _record_order_event(
        self,
        spread_id: int,
        event_type: str,
        payload: Dict[str, Any],
        created_at: str,
        idempotency_key: str,
    ):
        """Append an order event inside the caller's transaction."""
        self.conn.execute(
            """INSERT INTO order_events
               (spread_id, event_type, payload_json, created_at, idempotency_key)
               VALUES (?, ?, ?, ?, ?)""",
            (spread_id, event_type, json.dumps(payload, sort_keys=True, default=self._json_default),
             created_at, idempotency_key),
        )

    @staticmethod
    def _json_default(value: Any) -> Any:
        """Convert scalar library values into JSON-native types."""
        if hasattr(value, "item"):
            return value.item()
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

    def get_order_events(self, spread_id: Optional[int] = None) -> List[Dict[str, Any]]:
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

    def _record_leg_targets(
        self,
        spread_id: int,
        leg_role: str,
        asset_x: str,
        asset_y: str,
        side: str,
        weight_a: float,
        weight_b: float,
        created_at: str,
    ):
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

    def get_leg_fills(self, spread_id: Optional[int] = None) -> List[Dict[str, Any]]:
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

    def snapshot_equity(
        self,
        total_equity_pct: float,
        open_positions: int,
        realized_pnl_pct: float,
        unrealized_pnl_pct: float,
        notes: str = "",
        per_pair_pnl: Optional[str] = None,
    ):
        """Record a periodic mark-to-market equity snapshot."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO equity_snapshots
               (timestamp, total_equity_pct, open_positions, realized_pnl_pct,
                unrealized_pnl_pct, notes, per_pair_pnl)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (now, total_equity_pct, open_positions, realized_pnl_pct,
             unrealized_pnl_pct, notes, per_pair_pnl),
        )
        self.conn.commit()

    def get_equity_curve(self) -> List[Dict[str, Any]]:
        """Returns all equity snapshots for charting."""
        rows = self.conn.execute(
            "SELECT * FROM equity_snapshots ORDER BY timestamp"
        ).fetchall()
        return [dict(r) for r in rows]

    def record_tick_signal(
        self,
        pair_label: str,
        z_score: float,
        weight_a: float,
        weight_b: float,
        signal: str,
        action: str,
        price_a: float,
        price_b: float,
    ):
        """Record a single signal evaluation from a tick. Called for EVERY pair on EVERY tick."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO tick_signals
               (timestamp, pair_label, z_score, weight_a, weight_b, signal, action, price_a, price_b)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (now, pair_label, z_score, weight_a, weight_b, signal, action, price_a, price_b),
        )
        self.conn.commit()

    def get_tick_signals(self, pair_label: Optional[str] = None) -> List[Dict[str, Any]]:
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

    # ─── Reconciliation Interface ───────────────────────────────────

    def start_reconciliation_run(
        self,
        exchange_snapshot: Dict[str, Any],
        local_open_positions: List[Dict[str, Any]],
        status: str = "RUNNING",
    ) -> int:
        """Start an exchange/local reconciliation run."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            """INSERT INTO reconciliation_runs
               (started_at, exchange_snapshot_json, local_open_positions_json, status)
               VALUES (?, ?, ?, ?)""",
            (
                now,
                json.dumps(exchange_snapshot, sort_keys=True, default=self._json_default),
                json.dumps(local_open_positions, sort_keys=True, default=self._json_default),
                status,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def finish_reconciliation_run(self, run_id: int, status: str):
        """Mark a reconciliation run as finished."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """UPDATE reconciliation_runs
               SET finished_at=?, status=?
               WHERE id=?""",
            (now, status, run_id),
        )
        self.conn.commit()

    def record_reconciliation_delta(
        self,
        run_id: int,
        delta_type: str,
        payload: Dict[str, Any],
        symbol: Optional[str] = None,
        spread_id: Optional[int] = None,
        action_taken: Optional[str] = None,
    ) -> int:
        """Append one reconciliation delta for a run."""
        now = datetime.now(timezone.utc).isoformat()
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
                json.dumps(payload, sort_keys=True, default=self._json_default),
                now,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_reconciliation_runs(self) -> List[Dict[str, Any]]:
        """Return reconciliation runs in creation order."""
        rows = self.conn.execute(
            "SELECT * FROM reconciliation_runs ORDER BY started_at, id"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_reconciliation_deltas(self, run_id: Optional[int] = None) -> List[Dict[str, Any]]:
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

    # ─── Runtime State Interface ────────────────────────────────────

    def set_runtime_state(self, key: str, value: Any):
        """Persist a runtime key as JSON."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO runtime_state (key, value_json, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value_json=excluded.value_json,
                   updated_at=excluded.updated_at""",
            (key, json.dumps(value), now),
        )
        self.conn.commit()

    def get_runtime_state(self, key: str, default: Any = None) -> Any:
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

    def set_system_paused(self, paused: bool):
        """Persist whether the trader should skip tick execution."""
        self.set_runtime_state("system_paused", bool(paused))

    def is_system_paused(self) -> bool:
        """Return the durable pause flag. Defaults to running."""
        return bool(self.get_runtime_state("system_paused", False))

    def close(self):
        """Cleanly close the database connection."""
        self.conn.close()

    # ─── Commands Interface ──────────────────────────────────────────

    def write_command(self, command: str, target_pair: Optional[str] = None):
        """Write a new pending command from the UI."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO user_commands (timestamp, command, target_pair) VALUES (?, ?, ?)",
            (now, command, target_pair)
        )
        self.conn.commit()

    def claim_pending_commands(self) -> List[Dict[str, Any]]:
        """Claim all pending commands so execution can safely mark the final outcome."""
        now = datetime.now(timezone.utc).isoformat()
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
                    (now, *ids),
                )

        return commands

    def mark_command_executed(self, command_id: int):
        """Mark a claimed command as successfully executed."""
        self._mark_command_terminal(command_id, "EXECUTED")

    def mark_command_failed(self, command_id: int, error: str):
        """Mark a claimed command as failed."""
        self._mark_command_terminal(command_id, "FAILED", error=error)

    def mark_command_ignored(self, command_id: int, reason: str):
        """Mark a claimed command as intentionally ignored."""
        self._mark_command_terminal(command_id, "IGNORED", error=reason)

    def _mark_command_terminal(self, command_id: int, status: str, error: Optional[str] = None):
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """UPDATE user_commands
               SET status=?, completed_at=?, error=?
               WHERE id=?""",
            (status, now, error, command_id),
        )
        self.conn.commit()

    def get_commands(self) -> List[Dict[str, Any]]:
        """Return all user commands for tests and diagnostics."""
        rows = self.conn.execute(
            "SELECT * FROM user_commands ORDER BY timestamp"
        ).fetchall()
        return [dict(r) for r in rows]
