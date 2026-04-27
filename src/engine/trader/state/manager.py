"""SQLite-backed compatibility facade for trader state."""

from typing import Optional, List, Dict, Any

from src.engine.trader.state.connection import connect_sqlite
from src.engine.trader.state.lifecycle import compute_holding_bars
from src.engine.trader.state.migrations import migrate_schema
from src.engine.trader.state.repositories import build_state_repositories
from src.engine.trader.state.schema import create_schema
from src.engine.trader.state.serialization import json_default
from src.engine.trader.state.services import StateOperationService


class TradeStateManager:
    """
    ACID-compliant SQLite engine for trade lifecycle management.
    WAL mode ensures no corruption on process kill mid-write.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = connect_sqlite(self.db_path)
        self._create_tables()
        self._migrate_schema()
        repos = build_state_repositories(self.conn)
        self.positions = repos.positions
        self.events = repos.events
        self.legs = repos.legs
        self.equity = repos.equity
        self.signals = repos.signals
        self.runtime = repos.runtime
        self.commands = repos.commands
        self.reconciliation = repos.reconciliation
        self.lifecycle = repos.lifecycle
        self.operations = StateOperationService(repos)

    def _create_tables(self):
        create_schema(self.conn)

    def _migrate_schema(self):
        migrate_schema(self.conn)

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
        return self.lifecycle.open_position(
            pair_label=pair_label,
            asset_x=asset_x,
            asset_y=asset_y,
            side=side,
            entry_price_a=entry_price_a,
            entry_price_b=entry_price_b,
            weight_a=weight_a,
            weight_b=weight_b,
            entry_z=entry_z,
            lookback_bars=lookback_bars,
        )

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
        return self.lifecycle.close_position(
            pair_label=pair_label,
            exit_price_a=exit_price_a,
            exit_price_b=exit_price_b,
            exit_z=exit_z,
            close_reason=close_reason,
        )

    @staticmethod
    def _compute_holding_bars(open_ts: str, close_ts: str) -> int:
        return compute_holding_bars(open_ts, close_ts)

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Returns all currently open positions."""
        return self.positions.get_open()

    def get_position_for_pair(self, pair_label: str) -> Optional[Dict[str, Any]]:
        """Returns the open position for a specific pair, if any."""
        return self.positions.get_open_for_pair(pair_label)

    def get_all_closed(self) -> List[Dict[str, Any]]:
        """Returns all closed positions for the trade log."""
        return self.positions.get_closed()

    def get_all_orders(self) -> List[Dict[str, Any]]:
        """Returns ALL spread positions (OPEN + CLOSED) for the report engine."""
        return self.positions.get_all()

    def _record_order_event(
        self,
        spread_id: int,
        event_type: str,
        payload: Dict[str, Any],
        created_at: str,
        idempotency_key: str,
    ):
        """Append an order event inside the caller's transaction."""
        self.events.append(
            spread_id=spread_id,
            event_type=event_type,
            payload=payload,
            created_at=created_at,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def _json_default(value: Any) -> Any:
        return json_default(value)

    def get_order_events(self, spread_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return append-only order events, optionally filtered by spread id."""
        return self.events.get(spread_id=spread_id)

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
        self.legs.record_targets(
            spread_id=spread_id,
            leg_role=leg_role,
            asset_x=asset_x,
            asset_y=asset_y,
            side=side,
            weight_a=weight_a,
            weight_b=weight_b,
            created_at=created_at,
        )

    def get_leg_fills(self, spread_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return leg target/fill rows, optionally filtered by spread id."""
        return self.legs.get(spread_id=spread_id)

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
        self.operations.snapshot_equity(
            total_equity_pct=total_equity_pct,
            open_positions=open_positions,
            realized_pnl_pct=realized_pnl_pct,
            unrealized_pnl_pct=unrealized_pnl_pct,
            notes=notes,
            per_pair_pnl=per_pair_pnl,
        )

    def get_equity_curve(self) -> List[Dict[str, Any]]:
        """Returns all equity snapshots for charting."""
        return self.equity.get_curve()

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
        self.operations.record_tick_signal(
            pair_label=pair_label,
            z_score=z_score,
            weight_a=weight_a,
            weight_b=weight_b,
            signal=signal,
            action=action,
            price_a=price_a,
            price_b=price_b,
        )

    def get_tick_signals(self, pair_label: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve tick signals, optionally filtered by pair."""
        return self.signals.get(pair_label=pair_label)

    # ─── Reconciliation Interface ───────────────────────────────────

    def start_reconciliation_run(
        self,
        exchange_snapshot: Dict[str, Any],
        local_open_positions: List[Dict[str, Any]],
        status: str = "RUNNING",
    ) -> int:
        """Start an exchange/local reconciliation run."""
        return self.operations.start_reconciliation_run(
            exchange_snapshot=exchange_snapshot,
            local_open_positions=local_open_positions,
            status=status,
        )

    def finish_reconciliation_run(self, run_id: int, status: str):
        """Mark a reconciliation run as finished."""
        self.operations.finish_reconciliation_run(run_id=run_id, status=status)

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
        return self.operations.record_reconciliation_delta(
            run_id=run_id,
            delta_type=delta_type,
            payload=payload,
            symbol=symbol,
            spread_id=spread_id,
            action_taken=action_taken,
        )

    def get_reconciliation_runs(self) -> List[Dict[str, Any]]:
        """Return reconciliation runs in creation order."""
        return self.reconciliation.get_runs()

    def get_reconciliation_deltas(self, run_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return reconciliation deltas, optionally filtered by run."""
        return self.reconciliation.get_deltas(run_id=run_id)

    # ─── Runtime State Interface ────────────────────────────────────

    def set_runtime_state(self, key: str, value: Any):
        """Persist a runtime key as JSON."""
        self.operations.set_runtime_state(key=key, value=value)

    def get_runtime_state(self, key: str, default: Any = None) -> Any:
        """Read a runtime key from JSON, returning default when absent or malformed."""
        return self.operations.get_runtime_state(key=key, default=default)

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
        self.operations.write_command(command=command, target_pair=target_pair)

    def claim_pending_commands(self) -> List[Dict[str, Any]]:
        """Claim all pending commands so execution can safely mark the final outcome."""
        return self.operations.claim_pending_commands()

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
        self.operations.mark_command_terminal(
            command_id=command_id,
            status=status,
            error=error,
        )

    def get_commands(self) -> List[Dict[str, Any]]:
        """Return all user commands for tests and diagnostics."""
        return self.commands.get_all()
