"""Read-only reconciliation between local state and exchange snapshots."""

import asyncio
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from src.core.logger import logger
from src.engine.trader.state_manager import TradeStateManager


class ReconciliationDeltaType(StrEnum):
    """Supported exchange/local reconciliation classifications."""

    LOCAL_ONLY_POSITION = "LOCAL_ONLY_POSITION"
    EXCHANGE_ONLY_POSITION = "EXCHANGE_ONLY_POSITION"
    QTY_MISMATCH = "QTY_MISMATCH"
    SIDE_MISMATCH = "SIDE_MISMATCH"
    SYMBOL_MISMATCH = "SYMBOL_MISMATCH"
    MATCHED = "MATCHED"


class ExchangePositionSnapshot(BaseModel):
    """One exchange-side position from a read-only account snapshot."""

    model_config = ConfigDict(extra="allow")

    symbol: str
    side: str
    qty: float = Field(gt=0)
    spread_id: int | None = None

    @property
    def normalized_side(self) -> str:
        side = self.side.upper()
        if side in {"BUY", "LONG"}:
            return "BUY"
        if side in {"SELL", "SHORT"}:
            return "SELL"
        return side


class ExchangeSnapshotProvider(Protocol):
    """Read-only provider for exchange/account positions."""

    async def fetch_open_positions(self) -> list[ExchangePositionSnapshot]:
        """Fetch open exchange positions without mutating exchange state."""


class ReconciliationAuditReport(BaseModel):
    """Read-only auditor result for one reconciliation run."""

    run_id: int
    status: str
    unresolved_delta_count: int
    unresolved_deltas: list[dict[str, Any]]

    @property
    def has_unresolved_deltas(self) -> bool:
        """Return whether the audit found non-matching reconciliation deltas."""
        return self.unresolved_delta_count > 0


class ReadOnlyReconciliationAuditor:
    """Manually callable or scheduled read-only reconciliation auditor."""

    def __init__(
        self,
        state: TradeStateManager,
        snapshot_provider: ExchangeSnapshotProvider | None,
        credentials_available: bool,
        qty_tolerance: float = 1e-9,
    ):
        self.state = state
        self.snapshot_provider = snapshot_provider
        self.credentials_available = credentials_available
        self.qty_tolerance = qty_tolerance

    async def run_once(self) -> ReconciliationAuditReport:
        """Run one read-only audit and summarize unresolved deltas."""
        return await run_read_only_audit(
            state=self.state,
            snapshot_provider=self.snapshot_provider,
            credentials_available=self.credentials_available,
            qty_tolerance=self.qty_tolerance,
        )

    async def run_scheduled(
        self,
        interval_seconds: float,
        max_runs: int | None = None,
    ) -> list[ReconciliationAuditReport]:
        """Run audits on a fixed interval until cancelled or max_runs is reached."""
        reports = []
        runs_completed = 0
        while max_runs is None or runs_completed < max_runs:
            reports.append(await self.run_once())
            runs_completed += 1
            if max_runs is not None and runs_completed >= max_runs:
                break
            await asyncio.sleep(interval_seconds)
        return reports


def _local_open_leg_targets(state: TradeStateManager) -> list[dict[str, Any]]:
    """Build expected local open leg targets from open spread positions."""
    open_positions = state.get_open_positions()
    targets = []
    for position in open_positions:
        spread_id = position["id"]
        open_legs = [
            leg for leg in state.get_leg_fills(spread_id=spread_id)
            if leg["leg_role"] == "OPEN"
        ]
        for leg in open_legs:
            targets.append(
                {
                    "spread_id": spread_id,
                    "pair_label": position["pair_label"],
                    "symbol": leg["symbol"],
                    "side": leg["side"],
                    "target_qty": leg["target_qty"],
                }
            )
    return targets


def _positions_snapshot(positions: list[ExchangePositionSnapshot]) -> dict[str, Any]:
    return {"positions": [position.model_dump() for position in positions]}


def _classify_leg(
    local_leg: dict[str, Any],
    exchange_by_symbol: dict[str, ExchangePositionSnapshot],
    qty_tolerance: float,
) -> tuple[ReconciliationDeltaType, ExchangePositionSnapshot | None]:
    exchange_pos = exchange_by_symbol.get(local_leg["symbol"])
    if exchange_pos is None:
        return ReconciliationDeltaType.LOCAL_ONLY_POSITION, None

    if exchange_pos.normalized_side != local_leg["side"]:
        return ReconciliationDeltaType.SIDE_MISMATCH, exchange_pos

    if abs(exchange_pos.qty - float(local_leg["target_qty"])) > qty_tolerance:
        return ReconciliationDeltaType.QTY_MISMATCH, exchange_pos

    return ReconciliationDeltaType.MATCHED, exchange_pos


def _find_symbol_mismatches(
    local_legs: list[dict[str, Any]],
    exchange_positions: list[ExchangePositionSnapshot],
    consumed_symbols: set[str],
) -> list[tuple[dict[str, Any], ExchangePositionSnapshot]]:
    """Find exchange rows tied to a known spread_id but a different symbol."""
    mismatches = []
    local_spread_ids = {leg["spread_id"] for leg in local_legs}
    for exchange_pos in exchange_positions:
        if exchange_pos.symbol in consumed_symbols or exchange_pos.spread_id is None:
            continue
        if exchange_pos.spread_id in local_spread_ids:
            local_leg = next(leg for leg in local_legs if leg["spread_id"] == exchange_pos.spread_id)
            mismatches.append((local_leg, exchange_pos))
    return mismatches


async def run_boot_reconciliation(
    state: TradeStateManager,
    snapshot_provider: ExchangeSnapshotProvider | None,
    credentials_available: bool,
    qty_tolerance: float = 1e-9,
) -> int:
    """
    Record a read-only exchange/local reconciliation run.

    This function never submits, cancels, closes, or opens orders. It only reads
    local state, optionally reads an injected exchange snapshot, and writes
    reconciliation_runs / reconciliation_deltas diagnostics.
    """
    local_open_positions = state.get_open_positions()

    if snapshot_provider is None:
        run_id = state.start_reconciliation_run(
            exchange_snapshot={"positions": [], "skipped_reason": "NO_SNAPSHOT_PROVIDER"},
            local_open_positions=local_open_positions,
            status="SKIPPED_NO_SNAPSHOT_PROVIDER",
        )
        state.finish_reconciliation_run(run_id, status="SKIPPED_NO_SNAPSHOT_PROVIDER")
        return run_id

    if not credentials_available:
        run_id = state.start_reconciliation_run(
            exchange_snapshot={"positions": [], "skipped_reason": "NO_CREDENTIALS"},
            local_open_positions=local_open_positions,
            status="SKIPPED_NO_CREDENTIALS",
        )
        state.finish_reconciliation_run(run_id, status="SKIPPED_NO_CREDENTIALS")
        return run_id

    try:
        exchange_positions = await snapshot_provider.fetch_open_positions()
    except Exception as exc:
        run_id = state.start_reconciliation_run(
            exchange_snapshot={"positions": [], "error": str(exc)},
            local_open_positions=local_open_positions,
            status="FAILED",
        )
        state.finish_reconciliation_run(run_id, status="FAILED")
        return run_id

    run_id = state.start_reconciliation_run(
        exchange_snapshot=_positions_snapshot(exchange_positions),
        local_open_positions=local_open_positions,
        status="RUNNING",
    )

    local_legs = _local_open_leg_targets(state)
    exchange_by_symbol = {position.symbol: position for position in exchange_positions}
    consumed_symbols = set()
    has_unmatched_delta = False

    for local_leg in local_legs:
        delta_type, exchange_pos = _classify_leg(local_leg, exchange_by_symbol, qty_tolerance)
        if exchange_pos is not None:
            consumed_symbols.add(exchange_pos.symbol)
        if delta_type != ReconciliationDeltaType.MATCHED:
            has_unmatched_delta = True
        state.record_reconciliation_delta(
            run_id=run_id,
            delta_type=delta_type.value,
            symbol=local_leg["symbol"],
            spread_id=local_leg["spread_id"],
            action_taken="NO_ACTION",
            payload={
                "local_leg": local_leg,
                "exchange_position": exchange_pos.model_dump() if exchange_pos else None,
            },
        )

    for local_leg, exchange_pos in _find_symbol_mismatches(local_legs, exchange_positions, consumed_symbols):
        has_unmatched_delta = True
        consumed_symbols.add(exchange_pos.symbol)
        state.record_reconciliation_delta(
            run_id=run_id,
            delta_type=ReconciliationDeltaType.SYMBOL_MISMATCH.value,
            symbol=exchange_pos.symbol,
            spread_id=local_leg["spread_id"],
            action_taken="NO_ACTION",
            payload={
                "expected_local_leg": local_leg,
                "exchange_position": exchange_pos.model_dump(),
            },
        )

    for exchange_pos in exchange_positions:
        if exchange_pos.symbol in consumed_symbols:
            continue
        has_unmatched_delta = True
        state.record_reconciliation_delta(
            run_id=run_id,
            delta_type=ReconciliationDeltaType.EXCHANGE_ONLY_POSITION.value,
            symbol=exchange_pos.symbol,
            spread_id=exchange_pos.spread_id,
            action_taken="NO_ACTION",
            payload={"exchange_position": exchange_pos.model_dump()},
        )

    status = "DELTA_FOUND" if has_unmatched_delta else "MATCHED"
    state.finish_reconciliation_run(run_id, status=status)
    logger.info(f"Boot reconciliation completed with status={status}")
    return run_id


async def run_read_only_audit(
    state: TradeStateManager,
    snapshot_provider: ExchangeSnapshotProvider | None,
    credentials_available: bool,
    qty_tolerance: float = 1e-9,
) -> ReconciliationAuditReport:
    """
    Run the auditor in read-only mode and return unresolved deltas.

    The auditor intentionally delegates comparison and persistence to
    run_boot_reconciliation so it cannot submit, cancel, close, open, or repair
    positions. Its only writes are reconciliation_runs and reconciliation_deltas.
    """
    run_id = await run_boot_reconciliation(
        state=state,
        snapshot_provider=snapshot_provider,
        credentials_available=credentials_available,
        qty_tolerance=qty_tolerance,
    )
    run = next(row for row in state.get_reconciliation_runs() if row["id"] == run_id)
    deltas = state.get_reconciliation_deltas(run_id=run_id)
    unresolved_deltas = [
        delta for delta in deltas
        if delta["delta_type"] != ReconciliationDeltaType.MATCHED.value
    ]
    return ReconciliationAuditReport(
        run_id=run_id,
        status=run["status"],
        unresolved_delta_count=len(unresolved_deltas),
        unresolved_deltas=unresolved_deltas,
    )
