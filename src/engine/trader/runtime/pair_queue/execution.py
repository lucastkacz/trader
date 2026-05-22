"""Runtime consumption helpers for dynamic pair queue decisions."""

from typing import Any, Mapping, Protocol, Sequence

from src.engine.trader.runtime.pair_queue.models import (
    PairQueueDecision,
    PairQueueOpportunity,
    PairQueuePolicy,
)
from src.engine.trader.runtime.pair_queue.ranking import (
    build_open_position_exposures,
    build_pair_queue_opportunity,
    build_pair_queue_snapshot,
)
from src.engine.trader.runtime.pair_validity.models import PairValiditySnapshot


class TickEvaluation(Protocol):
    pair: dict[str, Any]
    pair_label: str
    current_side: str | None
    result: Any
    action: str


def build_queue_decisions_for_tick(
    *,
    evaluations: Sequence[TickEvaluation],
    open_positions: Sequence[Mapping[str, Any]],
    policy: PairQueuePolicy | None,
    validity_snapshots: Sequence[PairValiditySnapshot] | None,
    enabled: bool,
) -> dict[str, PairQueueDecision]:
    """Build queue decisions from current tick evidence without mutating state."""
    if not enabled or policy is None:
        return {}

    snapshot = build_pair_queue_snapshot(
        promoted_pairs=[evaluation.pair for evaluation in evaluations],
        validity_snapshots=validity_snapshots,
        opportunities={
            evaluation.pair_label: _opportunity_from_evaluation(evaluation)
            for evaluation in evaluations
        },
        open_positions=build_open_position_exposures(open_positions),
        policy=policy,
    )
    return {
        decision.pair_label: decision
        for decision in snapshot.decisions
    }


def order_evaluations_for_transition(
    evaluations: Sequence[TickEvaluation],
    queue_decisions: Mapping[str, PairQueueDecision],
) -> list[TickEvaluation]:
    original_index = {
        evaluation.pair_label: index
        for index, evaluation in enumerate(evaluations)
    }
    return sorted(
        evaluations,
        key=lambda evaluation: (
            evaluation.current_side is None and evaluation.action == "ENTRY",
            -_queue_rank(evaluation, queue_decisions, original_index),
        ),
    )


def allow_new_entry_from_queue(
    evaluation: TickEvaluation,
    decision: PairQueueDecision | None,
    queue_enabled: bool,
) -> bool:
    if evaluation.action not in {"ENTRY", "FLIP"}:
        return True
    if not queue_enabled:
        return True
    return decision is not None and decision.entry_allowed


def _opportunity_from_evaluation(evaluation: TickEvaluation) -> PairQueueOpportunity:
    entry_z = float(evaluation.pair["Best_Params"]["entry_z"])
    z_score = float(evaluation.result.z_score)
    return build_pair_queue_opportunity(
        pair_label=evaluation.pair_label,
        action=evaluation.action,
        z_score=z_score,
        entry_z=entry_z,
        note_prefix="current_tick",
    )


def _queue_rank(
    evaluation: TickEvaluation,
    queue_decisions: Mapping[str, PairQueueDecision],
    original_index: Mapping[str, int],
) -> int:
    decision = queue_decisions.get(evaluation.pair_label)
    if decision is None:
        return -original_index[evaluation.pair_label]
    return -decision.current_rank
