"""Pre-trade risk checks for runtime entry decisions."""

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

from src.engine.trader.config import RiskConfig


@dataclass(frozen=True)
class PreTradeRiskPolicy:
    """Runtime policy for state-only and live entry risk checks."""

    max_cluster_exposure: float
    max_portfolio_exposure: float
    max_leverage: float
    min_order_quantity: float
    min_order_notional: float
    order_quantity_step: float

    def __post_init__(self) -> None:
        if self.max_cluster_exposure <= 0:
            raise ValueError("max_cluster_exposure must be positive")
        if self.max_portfolio_exposure <= 0:
            raise ValueError("max_portfolio_exposure must be positive")
        if self.max_portfolio_exposure < self.max_cluster_exposure:
            raise ValueError(
                "max_portfolio_exposure must be greater than or equal to max_cluster_exposure"
            )
        if self.max_leverage <= 0:
            raise ValueError("max_leverage must be positive")
        if self.min_order_quantity <= 0:
            raise ValueError("min_order_quantity must be positive")
        if self.min_order_notional <= 0:
            raise ValueError("min_order_notional must be positive")
        if self.order_quantity_step <= 0:
            raise ValueError("order_quantity_step must be positive")


@dataclass(frozen=True)
class PreTradeRiskDecision:
    """Risk result for a proposed spread entry."""

    entry_allowed: bool
    block_reasons: list[str]
    sized_weight_a: float
    sized_weight_b: float
    proposed_notional_pct: float
    projected_portfolio_exposure: float
    projected_leverage: float


def pre_trade_policy_from_config(risk_cfg: RiskConfig) -> PreTradeRiskPolicy:
    """Convert typed operator risk config into runtime entry policy."""
    return PreTradeRiskPolicy(
        max_cluster_exposure=risk_cfg.max_cluster_exposure,
        max_portfolio_exposure=risk_cfg.max_portfolio_exposure,
        max_leverage=risk_cfg.max_leverage,
        min_order_quantity=risk_cfg.min_order_quantity,
        min_order_notional=risk_cfg.min_order_notional,
        order_quantity_step=risk_cfg.order_quantity_step,
    )


def evaluate_pre_trade_entry(
    *,
    result: Any,
    open_positions: Sequence[Mapping[str, Any]],
    policy: PreTradeRiskPolicy,
    replacing_pair_label: str | None = None,
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


def _is_valid_quantity_step(quantity: float, step: float) -> bool:
    if not _finite_positive(quantity) or not _finite_positive(step):
        return False
    step_count = quantity / step
    return math.isclose(step_count, round(step_count), rel_tol=0.0, abs_tol=1e-9)
