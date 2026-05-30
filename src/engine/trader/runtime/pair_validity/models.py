"""Typed outputs for read-only promoted-pair validity diagnostics."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PairValidityConfig:
    """Operator-supplied policy for read-only validity diagnostics."""

    recent_window_bars: int | None
    min_recent_bars: int
    max_latest_data_age_bars: int | None
    open_position_review_half_life_multiple: float | None

    def __post_init__(self) -> None:
        if self.recent_window_bars is not None and self.recent_window_bars <= 0:
            raise ValueError("recent_window_bars must be positive when provided")
        if self.min_recent_bars <= 0:
            raise ValueError("min_recent_bars must be positive")
        if (
            self.max_latest_data_age_bars is not None
            and self.max_latest_data_age_bars <= 0
        ):
            raise ValueError("max_latest_data_age_bars must be positive when provided")
        if (
            self.open_position_review_half_life_multiple is not None
            and self.open_position_review_half_life_multiple <= 0
        ):
            raise ValueError(
                "open_position_review_half_life_multiple must be positive when provided"
            )


@dataclass(frozen=True)
class PairValiditySnapshot:
    """Quantified diagnostics for one promoted pair."""

    pair_label: str
    asset_x: str
    asset_y: str
    artifact_generated_at: str
    artifact_promoted_at: str | None
    latest_data_at: str | None
    timeframe: str
    exchange: str
    recent_window_bars: int
    recent_observation_bars: int

    wall_clock_age_minutes_since_artifact_generation: float | None
    bars_since_artifact_generation: int | None
    bars_since_promotion: int | None
    research_window_start: str | None
    research_window_end: str | None
    wall_clock_age_minutes_since_research_end: float | None
    bars_since_research_end: int | None

    research_hedge_ratio: float | None
    recent_hedge_ratio: float | None
    hedge_ratio_drift_pct: float | None
    research_correlation: float | None
    recent_correlation: float | None
    correlation_delta: float | None
    research_p_value: float | None
    recent_p_value: float | None
    p_value_delta: float | None
    research_half_life_bars: float | None
    recent_half_life_bars: float | None
    half_life_drift_pct: float | None
    research_spread_mean: float | None
    recent_spread_mean: float | None
    spread_mean_shift_sigma: float | None
    research_spread_std: float | None
    recent_spread_std: float | None
    spread_std_drift_pct: float | None

    open_position_id: int | None
    open_position_holding_bars: int | None
    open_position_half_life_multiple: float | None
    observed_entries: int
    observed_signal_exits: int
    observed_forced_exits: int
    observed_avg_holding_bars: float | None

    operator_review_reasons: list[str] = field(default_factory=list)
    open_position_review_reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PairValidityReport:
    """Read-only validity diagnostics for a promoted artifact."""

    artifact_path: str
    timeframe: str
    exchange: str
    pair_count: int
    snapshots: list[PairValiditySnapshot]
    notes: list[str] = field(default_factory=list)
