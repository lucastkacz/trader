"""Build ranked dry-run decisions for promoted pair entries."""

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Literal, Mapping, Sequence

from src.engine.trader.runtime.pair_queue.models import (
    OpenPositionExposure,
    PairQueueDecision,
    PairQueueOpportunity,
    PairQueuePolicy,
    PairQueueSnapshot,
    PairQueueValidityThresholdEvidence,
)
from src.engine.trader.runtime.pair_validity.models import PairValiditySnapshot


def build_pair_queue_snapshot(
    *,
    promoted_pairs: Sequence[Mapping[str, Any]],
    validity_snapshots: Sequence[PairValiditySnapshot] | None = None,
    opportunities: Mapping[str, PairQueueOpportunity] | None = None,
    open_positions: Sequence[OpenPositionExposure] | None = None,
    policy: PairQueuePolicy | None = None,
    now: datetime | None = None,
) -> PairQueueSnapshot:
    """Rank promoted pairs for future entries without mutating runtime state."""
    resolved_policy = policy or PairQueuePolicy()
    validity_by_pair = {
        snapshot.pair_label: snapshot
        for snapshot in (validity_snapshots or [])
    }
    opportunities_by_pair = opportunities or {}
    exposures = list(open_positions or [])
    pair_exposure_counts = Counter(exposure.pair_label for exposure in exposures)
    asset_exposure_counts = Counter(
        asset
        for exposure in exposures
        for asset in (exposure.asset_x, exposure.asset_y)
    )

    decisions = [
        _build_decision(
            pair=pair,
            research_rank=index + 1,
            validity=validity_by_pair.get(_pair_label(pair)),
            opportunity=opportunities_by_pair.get(_pair_label(pair)),
            open_position_count=pair_exposure_counts[_pair_label(pair)],
            total_open_positions=len(exposures),
            asset_exposure_counts=asset_exposure_counts,
            policy=resolved_policy,
        )
        for index, pair in enumerate(promoted_pairs)
    ]
    ranked = sorted(
        decisions,
        key=lambda decision: (
            decision.entry_allowed,
            decision.score_total,
            -decision.research_rank,
            decision.pair_label,
        ),
        reverse=True,
    )
    reranked = [
        _with_current_rank(decision, current_rank=index + 1)
        for index, decision in enumerate(ranked)
    ]
    return PairQueueSnapshot(
        generated_at=now or datetime.now(timezone.utc),
        decisions=reranked,
    )


def build_open_position_exposures(
    open_positions: Sequence[Mapping[str, Any]],
) -> list[OpenPositionExposure]:
    """Convert runtime state rows into pair-queue exposure inputs."""
    return [
        OpenPositionExposure(
            pair_label=str(position["pair_label"]),
            asset_x=str(position["asset_x"]),
            asset_y=str(position["asset_y"]),
            position_id=(
                int(position["id"]) if position.get("id") is not None else None
            ),
        )
        for position in open_positions
    ]


def build_pair_queue_opportunity(
    *,
    pair_label: str,
    action: str,
    z_score: float,
    entry_z: float | None,
    note_prefix: str,
) -> PairQueueOpportunity:
    """Build current opportunity evidence from a signal action and z-score."""
    entry_signal = action in {"ENTRY", "FLIP"}
    if entry_signal:
        score = 1.0
    elif entry_z is not None and entry_z > 0:
        score = min(1.0, abs(z_score) / entry_z)
    else:
        score = 0.0
    return PairQueueOpportunity(
        pair_label=pair_label,
        score=score,
        entry_signal=entry_signal,
        notes=[
            f"{note_prefix}_action:{action}",
            f"{note_prefix}_z:{z_score:.4f}",
        ],
    )


def build_pair_queue_opportunities_from_signals(
    *,
    tick_signals: Sequence[Mapping[str, Any]],
    promoted_pairs: Sequence[Mapping[str, Any]],
) -> dict[str, PairQueueOpportunity]:
    """Build latest opportunity evidence from persisted tick signal rows."""
    entry_z_by_pair = {
        f"{pair['Asset_X']}|{pair['Asset_Y']}": float(pair["Best_Params"]["entry_z"])
        for pair in promoted_pairs
        if "Best_Params" in pair and "entry_z" in pair["Best_Params"]
    }
    latest_by_pair: dict[str, Mapping[str, Any]] = {}
    for signal in tick_signals:
        pair_label = str(signal["pair_label"])
        previous = latest_by_pair.get(pair_label)
        if previous is None or str(signal["timestamp"]) >= str(previous["timestamp"]):
            latest_by_pair[pair_label] = signal

    return {
        pair_label: build_pair_queue_opportunity(
            pair_label=pair_label,
            action=str(signal["action"]),
            z_score=float(signal["z_score"]),
            entry_z=entry_z_by_pair.get(pair_label),
            note_prefix="latest",
        )
        for pair_label, signal in latest_by_pair.items()
    }


def _build_decision(
    *,
    pair: Mapping[str, Any],
    research_rank: int,
    validity: PairValiditySnapshot | None,
    opportunity: PairQueueOpportunity | None,
    open_position_count: int,
    total_open_positions: int,
    asset_exposure_counts: Counter[str],
    policy: PairQueuePolicy,
) -> PairQueueDecision:
    label = _pair_label(pair)
    asset_x = str(pair["Asset_X"])
    asset_y = str(pair["Asset_Y"])
    block_reasons: list[str] = []
    review_reasons: list[str] = []
    notes: list[str] = []

    score_research = _research_score(pair, policy)
    score_validity, validity_threshold_evidence = _validity_score(
        validity=validity,
        policy=policy,
        block_reasons=block_reasons,
        review_reasons=review_reasons,
        notes=notes,
    )
    score_opportunity = _opportunity_score(
        opportunity=opportunity,
        policy=policy,
        block_reasons=block_reasons,
        notes=notes,
    )
    _append_allocation_reasons(
        asset_x=asset_x,
        asset_y=asset_y,
        open_position_count=open_position_count,
        total_open_positions=total_open_positions,
        asset_exposure_counts=asset_exposure_counts,
        policy=policy,
        block_reasons=block_reasons,
    )
    total = _weighted_score(
        research=score_research,
        validity=score_validity,
        opportunity=score_opportunity,
        policy=policy,
    )
    return PairQueueDecision(
        pair_label=label,
        asset_x=asset_x,
        asset_y=asset_y,
        research_rank=research_rank,
        current_rank=research_rank,
        score_total=total,
        score_research=score_research,
        score_validity=score_validity,
        score_opportunity=score_opportunity,
        entry_allowed=not block_reasons,
        has_open_position=open_position_count > 0,
        open_position_count=open_position_count,
        block_reasons=block_reasons,
        review_reasons=review_reasons,
        notes=notes,
        validity_threshold_evidence=validity_threshold_evidence,
    )


def _pair_label(pair: Mapping[str, Any]) -> str:
    return f"{pair['Asset_X']}|{pair['Asset_Y']}"


def _research_score(pair: Mapping[str, Any], policy: PairQueuePolicy) -> float:
    performance = pair.get("Performance")
    sharpe = None
    if isinstance(performance, Mapping):
        sharpe = performance.get("sharpe_ratio")
    return _clamp01(_optional_float(sharpe) / policy.research_sharpe_score_at)


def _validity_score(
    *,
    validity: PairValiditySnapshot | None,
    policy: PairQueuePolicy,
    block_reasons: list[str],
    review_reasons: list[str],
    notes: list[str],
) -> tuple[float, list[PairQueueValidityThresholdEvidence]]:
    if validity is None:
        notes.append("missing_pair_validity_snapshot")
        if policy.block_on_missing_validity:
            block_reasons.append("missing_pair_validity_snapshot")
        return 0.0, []

    review_reasons.extend(validity.operator_review_reasons)
    review_reasons.extend(validity.open_position_review_reasons)
    notes.extend(validity.notes)
    if policy.block_on_operator_review_reasons and validity.operator_review_reasons:
        block_reasons.append("pair_validity_operator_review_required")

    score = 1.0
    score -= 0.10 * len(validity.operator_review_reasons)
    score -= 0.05 * len(validity.open_position_review_reasons)
    score -= 0.02 * len(validity.notes)

    threshold_evidence = _build_validity_threshold_evidence(validity, policy)
    for evidence in threshold_evidence:
        if evidence.triggered:
            block_reasons.append(evidence.block_reason)
            score -= _validity_threshold_score_penalty(evidence.block_reason)

    return _clamp01(score), threshold_evidence


def _build_validity_threshold_evidence(
    validity: PairValiditySnapshot,
    policy: PairQueuePolicy,
) -> list[PairQueueValidityThresholdEvidence]:
    """Describe every optional validity threshold, including disabled ones."""
    return [
        _threshold_evidence(
            metric="bars_since_promotion",
            block_reason="bars_since_promotion_above_max",
            trigger_condition=">",
            measured_value=validity.bars_since_promotion,
            configured_threshold=policy.max_bars_since_promotion,
        ),
        _threshold_evidence(
            metric="recent_correlation",
            block_reason="recent_correlation_below_min",
            trigger_condition="<",
            measured_value=validity.recent_correlation,
            configured_threshold=policy.min_recent_correlation,
        ),
        _threshold_evidence(
            metric="recent_p_value",
            block_reason="recent_cointegration_p_value_above_max",
            trigger_condition=">",
            measured_value=validity.recent_p_value,
            configured_threshold=policy.max_recent_p_value,
        ),
        _threshold_evidence(
            metric="abs_hedge_ratio_drift_pct",
            block_reason="hedge_ratio_drift_above_max",
            trigger_condition=">",
            measured_value=(
                abs(validity.hedge_ratio_drift_pct)
                if validity.hedge_ratio_drift_pct is not None
                else None
            ),
            configured_threshold=policy.max_abs_hedge_ratio_drift_pct,
        ),
        _threshold_evidence(
            metric="half_life_drift_pct",
            block_reason="half_life_drift_above_max",
            trigger_condition=">",
            measured_value=validity.half_life_drift_pct,
            configured_threshold=policy.max_half_life_drift_pct,
        ),
    ]


def _threshold_evidence(
    *,
    metric: str,
    block_reason: str,
    trigger_condition: Literal[">", "<"],
    measured_value: int | float | None,
    configured_threshold: int | float | None,
) -> PairQueueValidityThresholdEvidence:
    enforced = configured_threshold is not None
    triggered = False
    if measured_value is not None and configured_threshold is not None:
        if trigger_condition == ">":
            triggered = measured_value > configured_threshold
        else:
            triggered = measured_value < configured_threshold
    return PairQueueValidityThresholdEvidence(
        metric=metric,
        block_reason=block_reason,
        trigger_condition=trigger_condition,
        measured_value=measured_value,
        configured_threshold=configured_threshold,
        enforced=enforced,
        triggered=triggered,
    )


def _validity_threshold_score_penalty(block_reason: str) -> float:
    if block_reason in {
        "bars_since_promotion_above_max",
        "recent_correlation_below_min",
        "recent_cointegration_p_value_above_max",
    }:
        return 0.25
    return 0.20


def _opportunity_score(
    *,
    opportunity: PairQueueOpportunity | None,
    policy: PairQueuePolicy,
    block_reasons: list[str],
    notes: list[str],
) -> float:
    if opportunity is None:
        if policy.require_entry_signal:
            block_reasons.append("missing_entry_opportunity")
        return 0.0
    notes.extend(opportunity.notes)
    if policy.require_entry_signal and not opportunity.entry_signal:
        block_reasons.append("no_entry_signal")
    return _clamp01(opportunity.score)


def _append_allocation_reasons(
    *,
    asset_x: str,
    asset_y: str,
    open_position_count: int,
    total_open_positions: int,
    asset_exposure_counts: Counter[str],
    policy: PairQueuePolicy,
    block_reasons: list[str],
) -> None:
    if (
        policy.max_open_positions is not None
        and total_open_positions >= policy.max_open_positions
    ):
        block_reasons.append("capital_slots_full")
    if open_position_count >= policy.max_positions_per_pair:
        block_reasons.append("pair_position_limit_reached")
    if policy.max_positions_per_asset is None:
        return
    if (
        asset_exposure_counts[asset_x] >= policy.max_positions_per_asset
        or asset_exposure_counts[asset_y] >= policy.max_positions_per_asset
    ):
        block_reasons.append("asset_position_limit_reached")


def _weighted_score(
    *,
    research: float,
    validity: float,
    opportunity: float,
    policy: PairQueuePolicy,
) -> float:
    total_weight = (
        policy.research_weight
        + policy.validity_weight
        + policy.opportunity_weight
    )
    score = (
        research * policy.research_weight
        + validity * policy.validity_weight
        + opportunity * policy.opportunity_weight
    ) / total_weight
    return round(_clamp01(score), 6)


def _with_current_rank(
    decision: PairQueueDecision,
    current_rank: int,
) -> PairQueueDecision:
    return PairQueueDecision(
        pair_label=decision.pair_label,
        asset_x=decision.asset_x,
        asset_y=decision.asset_y,
        research_rank=decision.research_rank,
        current_rank=current_rank,
        score_total=decision.score_total,
        score_research=decision.score_research,
        score_validity=decision.score_validity,
        score_opportunity=decision.score_opportunity,
        entry_allowed=decision.entry_allowed,
        has_open_position=decision.has_open_position,
        open_position_count=decision.open_position_count,
        block_reasons=decision.block_reasons,
        review_reasons=decision.review_reasons,
        notes=decision.notes,
        validity_threshold_evidence=decision.validity_threshold_evidence,
    )


def _optional_float(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
