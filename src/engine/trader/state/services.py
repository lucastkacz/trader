"""Timestamped state operation services."""

from datetime import datetime, timezone
from typing import Any

from src.engine.trader.state.order_lifecycle import (
    InvalidLegOrderTransition,
    LegOrderStatus,
    normalize_leg_order_status,
    validate_leg_order_transition,
)
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

    def transition_leg_order_status(
        self,
        leg_fill_id: int,
        next_status: LegOrderStatus | str,
        *,
        filled_qty: float | None = None,
        avg_fill_price: float | None = None,
        exchange_order_id: str | None = None,
        client_order_id: str | None = None,
        reason: str | None = None,
    ) -> bool:
        """
        Move one leg target through the local order lifecycle.

        Returns True when state changes, and False when the requested transition
        is an exact duplicate of the already-recorded state.
        """
        row = self.repos.legs.get_by_id(leg_fill_id)
        if row is None:
            raise KeyError(f"Leg fill id {leg_fill_id} does not exist")

        current_status = normalize_leg_order_status(row["status"])
        next_status = normalize_leg_order_status(next_status)
        next_values = _merge_leg_execution_values(
            row=row,
            next_status=next_status,
            filled_qty=filled_qty,
            avg_fill_price=avg_fill_price,
            exchange_order_id=exchange_order_id,
            client_order_id=client_order_id,
        )

        if _is_duplicate_leg_transition(
            row=row,
            next_status=next_status,
            values=next_values,
        ):
            return False

        if current_status == next_status and next_status != LegOrderStatus.PARTIALLY_FILLED:
            raise InvalidLegOrderTransition(
                f"Invalid leg order transition {current_status.value} -> {next_status.value}; "
                "status is already recorded with different execution fields"
            )

        validate_leg_order_transition(current_status, next_status)
        _validate_leg_execution_values(row=row, next_status=next_status, values=next_values)

        now = _utc_now()
        payload = {
            "leg_fill_id": leg_fill_id,
            "from_status": current_status.value,
            "to_status": next_status.value,
            "filled_qty": next_values["filled_qty"],
            "avg_fill_price": next_values["avg_fill_price"],
            "exchange_order_id": next_values["exchange_order_id"],
            "client_order_id": next_values["client_order_id"],
        }
        if reason:
            payload["reason"] = reason

        with self.repos.lifecycle.conn:
            self.repos.legs.update_execution_state(
                leg_fill_id=leg_fill_id,
                status=next_status.value,
                filled_qty=next_values["filled_qty"],
                avg_fill_price=next_values["avg_fill_price"],
                exchange_order_id=next_values["exchange_order_id"],
                client_order_id=next_values["client_order_id"],
                updated_at=now,
            )
            self.repos.events.append(
                spread_id=row["spread_id"],
                event_type=f"LEG_{next_status.value}",
                payload=payload,
                created_at=now,
                idempotency_key=_leg_transition_idempotency_key(
                    leg_fill_id=leg_fill_id,
                    current_status=current_status,
                    next_status=next_status,
                    values=next_values,
                ),
            )

        return True

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


def _merge_leg_execution_values(
    row: dict[str, Any],
    next_status: LegOrderStatus,
    filled_qty: float | None,
    avg_fill_price: float | None,
    exchange_order_id: str | None,
    client_order_id: str | None,
) -> dict[str, Any]:
    merged_filled_qty = row["filled_qty"] if filled_qty is None else filled_qty
    if next_status == LegOrderStatus.FILLED and filled_qty is None:
        merged_filled_qty = row["target_qty"]

    return {
        "filled_qty": float(merged_filled_qty),
        "avg_fill_price": row["avg_fill_price"] if avg_fill_price is None else avg_fill_price,
        "exchange_order_id": (
            row["exchange_order_id"] if exchange_order_id is None else exchange_order_id
        ),
        "client_order_id": row["client_order_id"] if client_order_id is None else client_order_id,
    }


def _is_duplicate_leg_transition(
    row: dict[str, Any],
    next_status: LegOrderStatus,
    values: dict[str, Any],
) -> bool:
    return (
        row["status"] == next_status.value
        and float(row["filled_qty"]) == values["filled_qty"]
        and row["avg_fill_price"] == values["avg_fill_price"]
        and row["exchange_order_id"] == values["exchange_order_id"]
        and row["client_order_id"] == values["client_order_id"]
    )


def _validate_leg_execution_values(
    row: dict[str, Any],
    next_status: LegOrderStatus,
    values: dict[str, Any],
) -> None:
    current_filled_qty = float(row["filled_qty"])
    target_qty = float(row["target_qty"])
    next_filled_qty = values["filled_qty"]
    tolerance = 1e-9

    if next_filled_qty < current_filled_qty - tolerance:
        raise ValueError("filled_qty cannot decrease during leg lifecycle transitions")
    if next_filled_qty < -tolerance:
        raise ValueError("filled_qty cannot be negative")
    if next_filled_qty > target_qty + tolerance:
        raise ValueError("filled_qty cannot exceed target_qty")

    if next_status == LegOrderStatus.PARTIALLY_FILLED:
        if next_filled_qty <= 0:
            raise ValueError("PARTIALLY_FILLED requires filled_qty greater than zero")
        if next_filled_qty >= target_qty - tolerance:
            raise ValueError("PARTIALLY_FILLED filled_qty must be less than target_qty")

    if next_status == LegOrderStatus.FILLED and abs(next_filled_qty - target_qty) > tolerance:
        raise ValueError("FILLED requires filled_qty to equal target_qty")


def _leg_transition_idempotency_key(
    leg_fill_id: int,
    current_status: LegOrderStatus,
    next_status: LegOrderStatus,
    values: dict[str, Any],
) -> str:
    return (
        f"leg:{leg_fill_id}:{current_status.value}->{next_status.value}:"
        f"filled={values['filled_qty']}:"
        f"avg={values['avg_fill_price']}:"
        f"exchange={values['exchange_order_id']}:"
        f"client={values['client_order_id']}"
    )
