"""Runtime-state summaries for pair-validity diagnostics."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.engine.trader.runtime.pair_validity.time import bars_between, parse_datetime


@dataclass(frozen=True)
class PairExecutionSummary:
    """Observed execution behavior for one promoted pair."""

    observed_entries: int
    observed_signal_exits: int
    observed_forced_exits: int
    observed_avg_holding_bars: float | None


def summarize_pair_execution(
    pair_label: str,
    all_positions: list[dict[str, Any]],
) -> PairExecutionSummary:
    pair_positions = [
        row for row in all_positions
        if row["pair_label"] == pair_label
    ]
    closed_pair_positions = [
        row for row in pair_positions
        if row["status"] == "CLOSED"
    ]
    return PairExecutionSummary(
        observed_entries=len(pair_positions),
        observed_signal_exits=sum(
            1 for row in closed_pair_positions
            if row["close_reason"] == "SIGNAL_EXIT"
        ),
        observed_forced_exits=sum(
            1 for row in closed_pair_positions
            if row["close_reason"] not in (None, "SIGNAL_EXIT")
        ),
        observed_avg_holding_bars=avg_holding_bars(closed_pair_positions),
    )


def open_position_holding_bars(
    *,
    open_position: dict[str, Any] | None,
    latest_data_at: datetime | None,
    now: datetime,
    timeframe: str,
    notes: list[str],
) -> int | None:
    if open_position is None:
        return None
    opened_at = parse_datetime(open_position["opened_at"])
    if opened_at is None:
        notes.append("open_position_missing_opened_at")
        return None
    end = latest_data_at or now
    return bars_between(opened_at, end, timeframe)


def avg_holding_bars(rows: list[dict[str, Any]]) -> float | None:
    bars = [
        float(row["holding_bars"])
        for row in rows
        if row["holding_bars"] is not None
    ]
    if not bars:
        return None
    return sum(bars) / len(bars)

