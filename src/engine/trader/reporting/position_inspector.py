"""Read-only open-position inspection for operator interfaces."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from typing import Any

from src.engine.trader.execution.pnl import calculate_position_pnl
from src.engine.trader.state_manager import TradeStateManager


@dataclass(frozen=True)
class PositionInspection:
    position: dict[str, Any]
    latest_signal: dict[str, Any] | None
    unrealized_pnl: float | None
    leg_status_counts: dict[str, dict[str, int]]
    has_exchange_identifiers: bool


def inspect_open_position(
    state: TradeStateManager,
    identifier: str,
) -> PositionInspection | None:
    """Build a read-only inspection snapshot for one open position."""
    position = _find_open_position(state.get_open_positions(), identifier)
    if position is None:
        return None

    latest_signal = _latest_signal(state.get_tick_signals(position["pair_label"]))
    unrealized_pnl = _unrealized_pnl_from_signal(position, latest_signal)
    if unrealized_pnl is None:
        unrealized_pnl = _unrealized_pnl_from_latest_equity(position["pair_label"], state.get_equity_curve())

    legs = state.get_leg_fills(spread_id=position["id"])
    return PositionInspection(
        position=position,
        latest_signal=latest_signal,
        unrealized_pnl=unrealized_pnl,
        leg_status_counts=_count_leg_statuses(legs),
        has_exchange_identifiers=any(
            leg.get("exchange_order_id") or leg.get("client_order_id")
            for leg in legs
        ),
    )


def _find_open_position(
    open_positions: list[dict[str, Any]],
    identifier: str,
) -> dict[str, Any] | None:
    normalized = identifier.strip().upper()
    if not normalized:
        return None

    for position in open_positions:
        if str(position["id"]) == normalized:
            return position

    for position in open_positions:
        if position["pair_label"].upper() == normalized:
            return position

    return None


def _latest_signal(signals: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not signals:
        return None
    return signals[-1]


def _unrealized_pnl_from_signal(
    position: dict[str, Any],
    latest_signal: dict[str, Any] | None,
) -> float | None:
    if latest_signal is None:
        return None
    return calculate_position_pnl(
        position=position,
        current_a=latest_signal["price_a"],
        current_b=latest_signal["price_b"],
    )


def _unrealized_pnl_from_latest_equity(
    pair_label: str,
    equity_curve: list[dict[str, Any]],
) -> float | None:
    for snapshot in reversed(equity_curve):
        raw_per_pair = snapshot.get("per_pair_pnl")
        if not raw_per_pair:
            continue
        try:
            per_pair = json.loads(raw_per_pair)
        except (json.JSONDecodeError, TypeError):
            continue
        if pair_label in per_pair:
            return per_pair[pair_label]
    return None


def _count_leg_statuses(legs: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for leg in legs:
        counts[leg["leg_role"]][leg["status"]] += 1
    return {
        role: dict(status_counts)
        for role, status_counts in sorted(counts.items())
    }
