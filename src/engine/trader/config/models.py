"""Pydantic models for operator-supplied YAML config."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictConfigModel(BaseModel):
    """Base model that rejects unknown config keys."""

    model_config = ConfigDict(extra="forbid")


class OrderExecutionConfig(StrictConfigModel):
    mode: Literal["state_only", "live"]
    fill_poll_attempts: int = Field(ge=0)
    fill_poll_interval_seconds: float = Field(ge=0)
    cancel_unfilled_after_poll: bool
    client_order_prefix: str = Field(min_length=1)


class MarketDataFetchConfig(StrictConfigModel):
    request_timeout_seconds: float = Field(gt=0)
    max_attempts: int = Field(gt=0)
    retry_backoff_seconds: float = Field(ge=0)

    def to_runtime_policy_kwargs(self) -> dict[str, object]:
        """Return kwargs for runtime readonly OHLCV fetch policy."""
        return {
            "request_timeout_seconds": self.request_timeout_seconds,
            "max_attempts": self.max_attempts,
            "retry_backoff_seconds": self.retry_backoff_seconds,
        }


class ReconciliationConfig(StrictConfigModel):
    snapshot_provider: Literal["none", "ccxt_readonly"]
    snapshot_timeout_seconds: float = Field(gt=0)
    stale_order_after_seconds: float = Field(gt=0)

    def to_runtime_policy_kwargs(self) -> dict[str, object]:
        """Return kwargs for runtime read-only reconciliation policy."""
        return {
            "snapshot_timeout_seconds": self.snapshot_timeout_seconds,
            "stale_order_after_seconds": self.stale_order_after_seconds,
        }


class PairRefreshConfig(StrictConfigModel):
    mode: Literal["manual"]
    reload_policy: Literal["on_boot"]
    stale_open_position_policy: Literal["natural_exit"]


class PairValidityDiagnosticsConfig(StrictConfigModel):
    recent_window_bars: int | None = Field(gt=0)
    min_recent_bars: int = Field(gt=0)
    max_latest_data_age_bars: int | None = Field(gt=0)
    open_position_review_half_life_multiple: float | None = Field(gt=0)

    def to_runtime_config_kwargs(self) -> dict[str, object]:
        """Return kwargs for runtime PairValidityConfig without importing runtime code."""
        return {
            "recent_window_bars": self.recent_window_bars,
            "min_recent_bars": self.min_recent_bars,
            "max_latest_data_age_bars": self.max_latest_data_age_bars,
            "open_position_review_half_life_multiple": (
                self.open_position_review_half_life_multiple
            ),
        }


class PairQueueScoringConfig(StrictConfigModel):
    research_weight: float = Field(ge=0)
    validity_weight: float = Field(ge=0)
    opportunity_weight: float = Field(ge=0)
    research_sharpe_score_at: float = Field(gt=0)

    @model_validator(mode="after")
    def at_least_one_weight_is_positive(self) -> "PairQueueScoringConfig":
        if self.research_weight + self.validity_weight + self.opportunity_weight <= 0:
            raise ValueError("at least one pair_queue scoring weight must be positive")
        return self


class PairQueueValidityThresholdsConfig(StrictConfigModel):
    block_on_missing_validity: bool
    block_on_operator_review_reasons: bool
    max_bars_since_promotion: int | None = Field(default=None, gt=0)
    min_recent_correlation: float | None = Field(default=None, ge=-1, le=1)
    max_recent_p_value: float | None = Field(default=None, ge=0, le=1)
    max_abs_hedge_ratio_drift_pct: float | None = Field(default=None, gt=0)
    max_half_life_drift_pct: float | None = Field(default=None, gt=0)


class PairQueueAllocationConfig(StrictConfigModel):
    max_open_positions: int | None = Field(default=None, gt=0)
    max_positions_per_pair: int = Field(gt=0)
    max_positions_per_asset: int | None = Field(default=None, gt=0)


class PairQueueConfig(StrictConfigModel):
    enabled: bool
    mode: Literal["report_only", "future_entries"]
    require_entry_signal: bool
    scoring: PairQueueScoringConfig
    validity_thresholds: PairQueueValidityThresholdsConfig
    allocation: PairQueueAllocationConfig

    def to_runtime_policy_kwargs(self) -> dict[str, object]:
        """Return kwargs for runtime PairQueuePolicy without importing runtime code."""
        return {
            "research_weight": self.scoring.research_weight,
            "validity_weight": self.scoring.validity_weight,
            "opportunity_weight": self.scoring.opportunity_weight,
            "research_sharpe_score_at": self.scoring.research_sharpe_score_at,
            "max_open_positions": self.allocation.max_open_positions,
            "max_positions_per_pair": self.allocation.max_positions_per_pair,
            "max_positions_per_asset": self.allocation.max_positions_per_asset,
            "require_entry_signal": self.require_entry_signal,
            "block_on_missing_validity": (
                self.validity_thresholds.block_on_missing_validity
            ),
            "block_on_operator_review_reasons": (
                self.validity_thresholds.block_on_operator_review_reasons
            ),
            "max_bars_since_promotion": (
                self.validity_thresholds.max_bars_since_promotion
            ),
            "min_recent_correlation": self.validity_thresholds.min_recent_correlation,
            "max_recent_p_value": self.validity_thresholds.max_recent_p_value,
            "max_abs_hedge_ratio_drift_pct": (
                self.validity_thresholds.max_abs_hedge_ratio_drift_pct
            ),
            "max_half_life_drift_pct": (
                self.validity_thresholds.max_half_life_drift_pct
            ),
        }


class PipelineDataConfig(StrictConfigModel):
    backfill_policy_config: str = Field(min_length=1)


class PipelineExecutionConfig(StrictConfigModel):
    market_data_base_dir: str = Field(min_length=1)
    artifact_base_dir: str = Field(min_length=1)
    db_path: str
    min_sharpe: float
    max_ticks: int | None = Field(gt=0)
    heartbeat_seconds: int = Field(gt=0)
    sync_to_boundary: bool
    market_data_fetch: MarketDataFetchConfig
    reconciliation: ReconciliationConfig
    order_execution: OrderExecutionConfig
    pair_refresh: PairRefreshConfig
    pair_validity: PairValidityDiagnosticsConfig
    pair_queue: PairQueueConfig


class PipelineConfig(StrictConfigModel):
    name: str
    timeframe: str
    historical_days: int
    data: PipelineDataConfig
    execution: PipelineExecutionConfig


class UniverseTickerLiquidityConfig(StrictConfigModel):
    enabled: bool
    min_24h_quote_volume: float = Field(ge=0)


class UniverseOHLCVLiquidityConfig(StrictConfigModel):
    enabled: bool
    timeframe: str = Field(min_length=1)
    lookback_bars: int = Field(gt=0)
    metric: Literal[
        "mean_quote_volume",
        "median_quote_volume",
        "percentile_quote_volume",
    ]
    min_value: float = Field(ge=0)
    percentile: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def validate_metric_parameters(self) -> "UniverseOHLCVLiquidityConfig":
        if self.metric == "percentile_quote_volume" and self.percentile is None:
            raise ValueError("percentile is required for percentile_quote_volume")
        if self.metric != "percentile_quote_volume" and self.percentile is not None:
            raise ValueError("percentile is only valid for percentile_quote_volume")
        return self


class UniverseMegaCapFilterConfig(StrictConfigModel):
    exclude_top_n: int = Field(ge=0)
    timeframe: str = Field(min_length=1)
    lookback_bars: int = Field(gt=0)
    metric: Literal[
        "mean_quote_volume",
        "median_quote_volume",
    ]


class UniverseDataMaturityConfig(StrictConfigModel):
    min_bars: int = Field(gt=0)


class UniverseFiltersConfig(StrictConfigModel):
    ticker_liquidity: UniverseTickerLiquidityConfig
    prefilter_liquidity: UniverseOHLCVLiquidityConfig
    stored_data_liquidity: UniverseOHLCVLiquidityConfig
    mega_caps: UniverseMegaCapFilterConfig
    data_maturity: UniverseDataMaturityConfig


class UniverseClusteringConfig(StrictConfigModel):
    returns_clip_percentile: float
    louvain_correlation_threshold: float


class UniverseCointegrationConfig(StrictConfigModel):
    p_value_threshold: float
    max_half_life_bars: int
    ewma_span_bars: int


class UniverseConfig(StrictConfigModel):
    name: str
    filters: UniverseFiltersConfig
    clustering: UniverseClusteringConfig
    cointegration: UniverseCointegrationConfig


class StrategyExecutionConfig(StrictConfigModel):
    entry_z_score: float
    exit_z_score: float
    stop_loss_z_score: float
    ew_ols_lookback_bars: int
    volatility_lookback_bars: int


class StrategyConfig(StrictConfigModel):
    name: str
    execution: StrategyExecutionConfig


class BacktestGridConfig(StrictConfigModel):
    entry_z_scores: list[float]
    lookback_bars: list[int]


class BacktestFrictionConfig(StrictConfigModel):
    maker_fee: float
    taker_fee: float
    annual_fund_rate: float


class BacktestConfig(StrictConfigModel):
    name: str
    grid_search: BacktestGridConfig
    friction: BacktestFrictionConfig


class RunProfileConfig(StrictConfigModel):
    pipeline: str = Field(min_length=1)
    venue: str = Field(min_length=1)
    market_profile: str = Field(min_length=1)
    universe: str = Field(min_length=1)
    backtest: str = Field(min_length=1)
    strategy: str = Field(min_length=1)
    skip_fetch: bool


class RiskConfig(StrictConfigModel):
    name: str
    max_cluster_exposure: float = Field(gt=0)
    max_portfolio_exposure: float = Field(gt=0)
    max_leverage: float = Field(gt=0)
    min_order_quantity: float = Field(gt=0)
    min_order_notional: float = Field(gt=0)
    order_quantity_step: float = Field(gt=0)
    liquidity_lookback_bars: int = Field(gt=0)
    min_recent_quote_volume: float = Field(gt=0)

    @model_validator(mode="after")
    def portfolio_exposure_covers_one_cluster(self) -> "RiskConfig":
        if self.max_portfolio_exposure < self.max_cluster_exposure:
            raise ValueError(
                "max_portfolio_exposure must be greater than or equal to "
                "max_cluster_exposure"
            )
        return self


class TelegramConfig(StrictConfigModel):
    environment: str
    bot_name: str
    db_path: str
    holding_period_bar_minutes: float
    promoted_pairs_path: str
    health_stale_after_minutes: float = Field(gt=0)
