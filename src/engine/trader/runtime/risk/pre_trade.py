"""Pre-trade risk checks for runtime entry decisions."""

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

from src.engine.trader.runtime.risk.models import (
    PreTradeLiquiditySnapshot,
    PreTradeRiskDecision,
    PreTradeRiskPolicy,
)


def evaluate_pre_trade_entry(
    *,
    result: Any,
    open_positions: Sequence[Mapping[str, Any]],
    policy: PreTradeRiskPolicy,
    replacing_pair_label: str | None = None,
    liquidity: PreTradeLiquiditySnapshot | None = None,
) -> PreTradeRiskDecision:
    """Size and validate a proposed entry against current runtime exposure."""
    raw_weight_a = float(result.weight_a)
    raw_weight_b = float(result.weight_b)
    raw_notional = abs(raw_weight_a) + abs(raw_weight_b)
    block_reasons: list[str] = []

    if not _finite_positive(raw_notional):
        block_reasons.append("invalid_signal_notional")
        return PreTradeRiskDecision(
            entry_allowed=False,
            block_reasons=block_reasons,
            sized_weight_a=0.0,
            sized_weight_b=0.0,
            proposed_notional_pct=0.0,
            projected_portfolio_exposure=_open_position_exposure(
                open_positions,
                replacing_pair_label=replacing_pair_label,
            ),
            projected_leverage=0.0,
        )

    scale = policy.max_cluster_exposure / raw_notional
    sized_weight_a = raw_weight_a * scale
    sized_weight_b = raw_weight_b * scale
    proposed_notional = abs(sized_weight_a) + abs(sized_weight_b)
    current_exposure = _open_position_exposure(
        open_positions,
        replacing_pair_label=replacing_pair_label,
    )
    projected_exposure = current_exposure + proposed_notional
    projected_leverage = projected_exposure

    if proposed_notional > policy.max_cluster_exposure + 1e-12:
        block_reasons.append("position_notional_above_max")
    if projected_exposure > policy.max_portfolio_exposure + 1e-12:
        block_reasons.append("portfolio_exposure_above_max")
    if projected_leverage > policy.max_leverage + 1e-12:
        block_reasons.append("max_leverage_exceeded")
    block_reasons.extend(
        _order_constraint_block_reasons(
            leg_targets=[
                _LegTarget(quantity=abs(sized_weight_a), price=float(result.price_a)),
                _LegTarget(quantity=abs(sized_weight_b), price=float(result.price_b)),
            ],
            policy=policy,
        )
    )
    block_reasons.extend(_liquidity_block_reasons(liquidity=liquidity, policy=policy))

    return PreTradeRiskDecision(
        entry_allowed=not block_reasons,
        block_reasons=block_reasons,
        sized_weight_a=sized_weight_a,
        sized_weight_b=sized_weight_b,
        proposed_notional_pct=proposed_notional,
        projected_portfolio_exposure=projected_exposure,
        projected_leverage=projected_leverage,
    )


def _open_position_exposure(
    open_positions: Sequence[Mapping[str, Any]],
    *,
    replacing_pair_label: str | None,
) -> float:
    exposure = 0.0
    for position in open_positions:
        if replacing_pair_label is not None and position["pair_label"] == replacing_pair_label:
            continue
        exposure += abs(float(position["weight_a"])) + abs(float(position["weight_b"]))
    return exposure


def _finite_positive(value: float) -> bool:
    return math.isfinite(value) and value > 0.0


@dataclass(frozen=True)
class _LegTarget:
    quantity: float
    price: float


def _order_constraint_block_reasons(
    *,
    leg_targets: Sequence[_LegTarget],
    policy: PreTradeRiskPolicy,
) -> list[str]:
    reasons: list[str] = []
    if any(not _finite_positive(target.quantity) for target in leg_targets):
        reasons.append("order_quantity_below_min")
    elif any(target.quantity < policy.min_order_quantity for target in leg_targets):
        reasons.append("order_quantity_below_min")

    if any(not _finite_positive(target.price) for target in leg_targets):
        reasons.append("order_notional_below_min")
    elif any(
        target.quantity * target.price < policy.min_order_notional
        for target in leg_targets
    ):
        reasons.append("order_notional_below_min")

    if any(
        not _is_valid_quantity_step(target.quantity, policy.order_quantity_step)
        for target in leg_targets
    ):
        reasons.append("order_precision_invalid")

    return reasons


def _liquidity_block_reasons(
    *,
    liquidity: PreTradeLiquiditySnapshot | None,
    policy: PreTradeRiskPolicy,
) -> list[str]:
    if liquidity is None:
        return ["liquidity_snapshot_missing"]
    quote_volumes = [liquidity.quote_volume_a, liquidity.quote_volume_b]
    if any(volume is None or not _finite_positive(volume) for volume in quote_volumes):
        return ["liquidity_snapshot_missing"]
    if any(volume < policy.min_recent_quote_volume for volume in quote_volumes):
        return ["liquidity_below_min"]
    return []


def _is_valid_quantity_step(quantity: float, step: float) -> bool:
    if not _finite_positive(quantity) or not _finite_positive(step):
        return False
    step_count = quantity / step
    return math.isclose(step_count, round(step_count), rel_tol=0.0, abs_tol=1e-9)
