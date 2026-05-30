"""Typed runtime risk models for pre-trade entry checks."""

from dataclasses import dataclass

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
    liquidity_lookback_bars: int
    min_recent_quote_volume: float

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
        if self.liquidity_lookback_bars <= 0:
            raise ValueError("liquidity_lookback_bars must be positive")
        if self.min_recent_quote_volume <= 0:
            raise ValueError("min_recent_quote_volume must be positive")


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


@dataclass(frozen=True)
class PreTradeLiquiditySnapshot:
    """Recent quote-volume evidence for both proposed entry legs."""

    quote_volume_a: float | None
    quote_volume_b: float | None
    observation_bars: int


@dataclass(frozen=True)
class RiskKillSwitchState:
    """Typed durable risk kill-switch state."""

    active: bool
    reason: str | None = None
    activated_at: str | None = None


def pre_trade_policy_from_config(risk_cfg: RiskConfig) -> PreTradeRiskPolicy:
    """Convert typed operator risk config into runtime entry policy."""
    return PreTradeRiskPolicy(
        max_cluster_exposure=risk_cfg.max_cluster_exposure,
        max_portfolio_exposure=risk_cfg.max_portfolio_exposure,
        max_leverage=risk_cfg.max_leverage,
        min_order_quantity=risk_cfg.min_order_quantity,
        min_order_notional=risk_cfg.min_order_notional,
        order_quantity_step=risk_cfg.order_quantity_step,
        liquidity_lookback_bars=risk_cfg.liquidity_lookback_bars,
        min_recent_quote_volume=risk_cfg.min_recent_quote_volume,
    )
