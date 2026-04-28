"""Pydantic models for operator-supplied YAML config."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictConfigModel(BaseModel):
    """Base model that rejects unknown config keys."""

    model_config = ConfigDict(extra="forbid")


class OrderExecutionConfig(StrictConfigModel):
    mode: Literal["state_only", "live"]
    fill_poll_attempts: int = Field(ge=0)
    fill_poll_interval_seconds: float = Field(ge=0)
    cancel_unfilled_after_poll: bool
    client_order_prefix: str = Field(min_length=1)


class PipelineExecutionConfig(StrictConfigModel):
    exchange: str
    credential_tier: Literal["readonly", "live"]
    db_path: str
    min_sharpe: float
    max_ticks: int | None
    heartbeat_seconds: int
    sync_to_boundary: bool
    order_execution: OrderExecutionConfig


class PipelineConfig(StrictConfigModel):
    name: str
    timeframe: str
    historical_days: int
    max_symbols: int | None
    execution: PipelineExecutionConfig


class UniverseFiltersConfig(StrictConfigModel):
    exclude_top_n_mega_caps: int
    volume_lookback_bars: int
    min_volume_liquidity: float
    max_volume_liquidity: float
    min_data_maturity_bars: int


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


class RiskConfig(StrictConfigModel):
    name: str
    max_cluster_exposure: float
    max_leverage: float


class TelegramConfig(StrictConfigModel):
    environment: str
    bot_name: str
    db_path: str
    holding_period_bar_minutes: float
