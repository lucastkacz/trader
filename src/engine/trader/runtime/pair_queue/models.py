"""Typed models for dynamic promoted-pair queue decisions."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class PairQueuePolicy:
    """Runtime policy for dry-run pair ranking and entry eligibility."""

    research_weight: float = 0.35
    validity_weight: float = 0.45
    opportunity_weight: float = 0.20
    research_sharpe_score_at: float = 3.0
    max_open_positions: int | None = None
    max_positions_per_pair: int = 1
    max_positions_per_asset: int | None = None
    require_entry_signal: bool = False
    block_on_missing_validity: bool = True
    block_on_operator_review_reasons: bool = True
    max_bars_since_promotion: int | None = None
    min_recent_correlation: float | None = None
    max_recent_p_value: float | None = None
    max_abs_hedge_ratio_drift_pct: float | None = None
    max_half_life_drift_pct: float | None = None

    def __post_init__(self) -> None:
        weights = (
            self.research_weight,
            self.validity_weight,
            self.opportunity_weight,
        )
        if any(weight < 0 for weight in weights):
            raise ValueError("pair queue weights must be non-negative")
        if sum(weights) <= 0:
            raise ValueError("at least one pair queue weight must be positive")
        if self.research_sharpe_score_at <= 0:
            raise ValueError("research_sharpe_score_at must be positive")
        if self.max_open_positions is not None and self.max_open_positions <= 0:
            raise ValueError("max_open_positions must be positive when provided")
        if self.max_positions_per_pair <= 0:
            raise ValueError("max_positions_per_pair must be positive")
        if (
            self.max_positions_per_asset is not None
            and self.max_positions_per_asset <= 0
        ):
            raise ValueError(
                "max_positions_per_asset must be positive when provided"
            )
        if (
            self.max_bars_since_promotion is not None
            and self.max_bars_since_promotion <= 0
        ):
            raise ValueError("max_bars_since_promotion must be positive when provided")


@dataclass(frozen=True)
class PairQueueOpportunity:
    """Current opportunity evidence for a promoted pair."""

    pair_label: str
    score: float
    entry_signal: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OpenPositionExposure:
    """Open runtime exposure that consumes pair queue capacity."""

    pair_label: str
    asset_x: str
    asset_y: str
    position_id: int | None = None


@dataclass(frozen=True)
class PairQueueDecision:
    """Auditable dry-run decision for one promoted pair."""

    pair_label: str
    asset_x: str
    asset_y: str
    research_rank: int
    current_rank: int
    score_total: float
    score_research: float
    score_validity: float
    score_opportunity: float
    entry_allowed: bool
    has_open_position: bool
    open_position_count: int
    block_reasons: list[str] = field(default_factory=list)
    review_reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PairQueueSnapshot:
    """Ranked dry-run view of the promoted pair universe."""

    generated_at: datetime
    decisions: list[PairQueueDecision]

