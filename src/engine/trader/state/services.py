"""Timestamped state operation services."""

from datetime import datetime, timezone
from typing import Any

from src.engine.trader.state.repositories import StateRepositories


class StateOperationService:
    """Coordinate timestamped operations over state repositories."""

    def __init__(self, repos: StateRepositories):
        self.repos = repos

    def snapshot_equity(
        self,
        total_equity_pct: float,
        open_positions: int,
        realized_pnl_pct: float,
        unrealized_pnl_pct: float,
        notes: str,
        per_pair_pnl: str | None,
    ) -> None:
        """Record a periodic mark-to-market equity snapshot."""
        self.repos.equity.snapshot(
            timestamp=_utc_now(),
            total_equity_pct=total_equity_pct,
            open_positions=open_positions,
            realized_pnl_pct=realized_pnl_pct,
            unrealized_pnl_pct=unrealized_pnl_pct,
            notes=notes,
            per_pair_pnl=per_pair_pnl,
        )

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
    ) -> None:
        """Record a single signal evaluation from a tick."""
        self.repos.signals.record(
            timestamp=_utc_now(),
            pair_label=pair_label,
            z_score=z_score,
            weight_a=weight_a,
            weight_b=weight_b,
            signal=signal,
            action=action,
            price_a=price_a,
            price_b=price_b,
        )

    def start_reconciliation_run(
        self,
        exchange_snapshot: dict[str, Any],
        local_open_positions: list[dict[str, Any]],
        status: str,
    ) -> int:
        """Start an exchange/local reconciliation run."""
        return self.repos.reconciliation.start_run(
            started_at=_utc_now(),
            exchange_snapshot=exchange_snapshot,
            local_open_positions=local_open_positions,
            status=status,
        )

    def finish_reconciliation_run(self, run_id: int, status: str) -> None:
        """Mark a reconciliation run as finished."""
        self.repos.reconciliation.finish_run(
            run_id=run_id,
            finished_at=_utc_now(),
            status=status,
        )

    def record_reconciliation_delta(
        self,
        run_id: int,
        delta_type: str,
        payload: dict[str, Any],
        symbol: str | None = None,
        spread_id: int | None = None,
        action_taken: str | None = None,
    ) -> int:
        """Append one reconciliation delta for a run."""
        return self.repos.reconciliation.record_delta(
            run_id=run_id,
            delta_type=delta_type,
            payload=payload,
            created_at=_utc_now(),
            symbol=symbol,
            spread_id=spread_id,
            action_taken=action_taken,
        )

    def set_runtime_state(self, key: str, value: Any) -> None:
        """Persist a runtime key as JSON."""
        self.repos.runtime.set(key=key, value=value, updated_at=_utc_now())

    def get_runtime_state(self, key: str, default: Any = None) -> Any:
        """Read a runtime key from JSON, returning default when absent or malformed."""
        return self.repos.runtime.get(key=key, default=default)

    def write_command(self, command: str, target_pair: str | None = None) -> None:
        """Write a new pending command from the UI."""
        self.repos.commands.write(
            timestamp=_utc_now(),
            command=command,
            target_pair=target_pair,
        )

    def claim_pending_commands(self) -> list[dict[str, Any]]:
        """Claim all pending commands so execution can safely mark the final outcome."""
        return self.repos.commands.claim_pending(claimed_at=_utc_now())

    def mark_command_terminal(
        self,
        command_id: int,
        status: str,
        error: str | None = None,
    ) -> None:
        """Mark a claimed command as terminal."""
        self.repos.commands.mark_terminal(
            command_id=command_id,
            status=status,
            completed_at=_utc_now(),
            error=error,
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
