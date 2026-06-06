from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.engine.trader.config import (
    PipelineConfig,
    load_backtest_config,
    load_pipeline_config,
    load_risk_config,
    load_run_profile_config,
    load_strategy_config,
    load_telegram_config,
    load_universe_config,
)


def write_yaml(tmp_path, data):
    path = tmp_path / "config.yml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_valid_operator_configs_parse():
    dev_pipeline = load_pipeline_config("configs/pipelines/dev.yml")
    assert dev_pipeline.execution.max_ticks is None
    assert dev_pipeline.venue.exchange_id == "bybit"
    assert (
        dev_pipeline.venue.market_profile_config
        == "configs/exchange/market_profiles/linear_usdt_swap.yml"
    )
    assert dev_pipeline.venue.credential_tier == "readonly"
    assert dev_pipeline.data.backfill_policy_config == "configs/data/backfill_default.yml"
    assert dev_pipeline.execution.market_data_base_dir == "data/parquet"
    assert dev_pipeline.execution.artifact_base_dir == "data/universes"
    assert dev_pipeline.execution.market_data_fetch.request_timeout_seconds == 15.0
    assert dev_pipeline.execution.market_data_fetch.max_attempts == 3
    assert dev_pipeline.execution.market_data_fetch.retry_backoff_seconds == 2.0
    assert dev_pipeline.execution.reconciliation.snapshot_provider == "ccxt_readonly"
    assert dev_pipeline.execution.reconciliation.snapshot_timeout_seconds == 15.0
    assert dev_pipeline.execution.reconciliation.stale_order_after_seconds == 120.0
    assert dev_pipeline.execution.order_execution.mode == "state_only"
    assert load_pipeline_config("configs/pipelines/uat.yml").execution.max_ticks is None
    assert load_pipeline_config("configs/pipelines/prod.yml").execution.max_ticks is None

    universe_cfg = load_universe_config("configs/universe/alpha_v1.yml")
    assert universe_cfg.filters.min_volume_liquidity == 20_000_000
    assert universe_cfg.cointegration.ewma_span_bars == 48
    assert load_strategy_config("configs/strategy/dev.yml").execution.volatility_lookback_bars == 60
    assert load_strategy_config("configs/strategy/uat.yml").name == "UAT Institutional Mean Reversion V1"
    assert load_strategy_config("configs/strategy/prod.yml").name == "PROD Institutional Mean Reversion V1"
    assert load_backtest_config("configs/backtest/stress_test.yml").friction.taker_fee == 0.0006
    run_profile = load_run_profile_config("configs/runs/dev_1m_research.yml")
    assert run_profile.pipeline == "configs/pipelines/dev.yml"
    assert run_profile.skip_fetch is False
    assert load_risk_config("configs/risk/alpha_v1.yml").max_leverage == 10.0
    assert load_risk_config("configs/risk/alpha_v1.yml").max_cluster_exposure == 0.10
    assert load_risk_config("configs/risk/alpha_v1.yml").max_portfolio_exposure == 0.30
    assert load_risk_config("configs/risk/alpha_v1.yml").min_order_quantity == 0.000001
    assert load_risk_config("configs/risk/alpha_v1.yml").min_order_notional == 0.000001
    assert load_risk_config("configs/risk/alpha_v1.yml").order_quantity_step == 0.000001
    assert load_risk_config("configs/risk/alpha_v1.yml").liquidity_lookback_bars == 20
    assert load_risk_config("configs/risk/alpha_v1.yml").min_recent_quote_volume == 1.0
    assert load_telegram_config("configs/telegram/dev.yml").environment == "DEV"
    assert load_telegram_config("configs/telegram/dev.yml").holding_period_bar_minutes == 1
    assert (
        load_telegram_config("configs/telegram/dev.yml").promoted_pairs_path
        == "data/universes/1m/surviving_pairs.json"
    )
    assert load_telegram_config("configs/telegram/dev.yml").health_stale_after_minutes == 5
    assert load_telegram_config("configs/telegram/uat.yml").environment == "UAT"
    assert load_telegram_config("configs/telegram/uat.yml").holding_period_bar_minutes == 240
    assert load_telegram_config("configs/telegram/uat.yml").health_stale_after_minutes == 720
    assert load_telegram_config("configs/telegram/prod.yml").environment == "PROD"
    assert load_telegram_config("configs/telegram/prod.yml").holding_period_bar_minutes == 240


def test_all_shipped_pipeline_configs_keep_order_execution_state_only():
    pipeline_paths = sorted(Path("configs/pipelines").glob("*.yml"))
    assert [path.name for path in pipeline_paths] == ["dev.yml", "prod.yml", "uat.yml"]

    parsed = [load_pipeline_config(path) for path in pipeline_paths]

    assert {cfg.execution.order_execution.mode for cfg in parsed} == {"state_only"}


def test_all_shipped_strategy_configs_parse():
    strategy_paths = sorted(Path("configs/strategy").glob("*.yml"))
    assert [path.name for path in strategy_paths] == ["dev.yml", "prod.yml", "uat.yml"]

    parsed = [load_strategy_config(path) for path in strategy_paths]

    assert {cfg.execution.exit_z_score for cfg in parsed} == {0.0}


def test_unsupported_order_execution_mode_fails_loudly(tmp_path):
    cfg = yaml.safe_load(open("configs/pipelines/dev.yml"))
    cfg["pipeline"]["execution"]["order_execution"]["mode"] = "live_without_gate"
    path = write_yaml(tmp_path, cfg)

    with pytest.raises(ValidationError, match="mode"):
        load_pipeline_config(path)


def test_unsupported_reconciliation_snapshot_provider_fails_loudly(tmp_path):
    cfg = yaml.safe_load(open("configs/pipelines/dev.yml"))
    cfg["pipeline"]["execution"]["reconciliation"]["snapshot_provider"] = "mutating_client"
    path = write_yaml(tmp_path, cfg)

    with pytest.raises(ValidationError, match="snapshot_provider"):
        load_pipeline_config(path)


def test_pipeline_max_ticks_must_be_present_but_may_be_null(tmp_path):
    cfg = yaml.safe_load(open("configs/pipelines/dev.yml"))
    path = write_yaml(tmp_path, cfg)
    parsed = load_pipeline_config(path)
    assert isinstance(parsed, PipelineConfig)
    assert parsed.execution.max_ticks is None

    missing_cfg = deepcopy(cfg)
    del missing_cfg["pipeline"]["execution"]["max_ticks"]
    missing_path = write_yaml(tmp_path, missing_cfg)

    with pytest.raises(ValidationError, match="max_ticks"):
        load_pipeline_config(missing_path)


@pytest.mark.parametrize(
    ("source_path", "top_key", "field_path", "loader", "match"),
    [
        (
            "configs/pipelines/dev.yml",
            "pipeline",
            ("venue",),
            load_pipeline_config,
            "venue",
        ),
        (
            "configs/pipelines/dev.yml",
            "pipeline",
            ("venue", "exchange_id"),
            load_pipeline_config,
            "exchange_id",
        ),
        (
            "configs/pipelines/dev.yml",
            "pipeline",
            ("venue", "market_profile_config"),
            load_pipeline_config,
            "market_profile_config",
        ),
        (
            "configs/pipelines/dev.yml",
            "pipeline",
            ("venue", "credential_tier"),
            load_pipeline_config,
            "credential_tier",
        ),
        (
            "configs/pipelines/dev.yml",
            "pipeline",
            ("data",),
            load_pipeline_config,
            "data",
        ),
        (
            "configs/pipelines/dev.yml",
            "pipeline",
            ("data", "backfill_policy_config"),
            load_pipeline_config,
            "backfill_policy_config",
        ),
        (
            "configs/pipelines/dev.yml",
            "pipeline",
            ("execution", "order_execution"),
            load_pipeline_config,
            "order_execution",
        ),
        (
            "configs/pipelines/dev.yml",
            "pipeline",
            ("execution", "order_execution", "mode"),
            load_pipeline_config,
            "mode",
        ),
        (
            "configs/pipelines/dev.yml",
            "pipeline",
            ("execution", "market_data_base_dir"),
            load_pipeline_config,
            "market_data_base_dir",
        ),
        (
            "configs/pipelines/dev.yml",
            "pipeline",
            ("execution", "market_data_fetch"),
            load_pipeline_config,
            "market_data_fetch",
        ),
        (
            "configs/pipelines/dev.yml",
            "pipeline",
            ("execution", "market_data_fetch", "request_timeout_seconds"),
            load_pipeline_config,
            "request_timeout_seconds",
        ),
        (
            "configs/pipelines/dev.yml",
            "pipeline",
            ("execution", "market_data_fetch", "max_attempts"),
            load_pipeline_config,
            "max_attempts",
        ),
        (
            "configs/pipelines/dev.yml",
            "pipeline",
            ("execution", "market_data_fetch", "retry_backoff_seconds"),
            load_pipeline_config,
            "retry_backoff_seconds",
        ),
        (
            "configs/pipelines/dev.yml",
            "pipeline",
            ("execution", "reconciliation"),
            load_pipeline_config,
            "reconciliation",
        ),
        (
            "configs/pipelines/dev.yml",
            "pipeline",
            ("execution", "reconciliation", "snapshot_provider"),
            load_pipeline_config,
            "snapshot_provider",
        ),
        (
            "configs/pipelines/dev.yml",
            "pipeline",
            ("execution", "reconciliation", "snapshot_timeout_seconds"),
            load_pipeline_config,
            "snapshot_timeout_seconds",
        ),
        (
            "configs/pipelines/dev.yml",
            "pipeline",
            ("execution", "reconciliation", "stale_order_after_seconds"),
            load_pipeline_config,
            "stale_order_after_seconds",
        ),
        (
            "configs/pipelines/dev.yml",
            "pipeline",
            ("execution", "artifact_base_dir"),
            load_pipeline_config,
            "artifact_base_dir",
        ),
        (
            "configs/universe/alpha_v1.yml",
            "universe",
            ("filters", "min_volume_liquidity"),
            load_universe_config,
            "min_volume_liquidity",
        ),
        (
            "configs/universe/alpha_v1.yml",
            "universe",
            ("cointegration", "ewma_span_bars"),
            load_universe_config,
            "ewma_span_bars",
        ),
        (
            "configs/strategy/dev.yml",
            "strategy",
            ("execution", "volatility_lookback_bars"),
            load_strategy_config,
            "volatility_lookback_bars",
        ),
        (
            "configs/backtest/stress_test.yml",
            "backtest",
            ("friction", "taker_fee"),
            load_backtest_config,
            "taker_fee",
        ),
        (
            "configs/runs/dev_1m_research.yml",
            "run",
            ("pipeline",),
            load_run_profile_config,
            "pipeline",
        ),
        (
            "configs/runs/dev_1m_research.yml",
            "run",
            ("skip_fetch",),
            load_run_profile_config,
            "skip_fetch",
        ),
        (
            "configs/telegram/dev.yml",
            "telegram",
            ("db_path",),
            load_telegram_config,
            "db_path",
        ),
        (
            "configs/telegram/dev.yml",
            "telegram",
            ("environment",),
            load_telegram_config,
            "environment",
        ),
        (
            "configs/telegram/dev.yml",
            "telegram",
            ("holding_period_bar_minutes",),
            load_telegram_config,
            "holding_period_bar_minutes",
        ),
        (
            "configs/telegram/dev.yml",
            "telegram",
            ("promoted_pairs_path",),
            load_telegram_config,
            "promoted_pairs_path",
        ),
        (
            "configs/telegram/dev.yml",
            "telegram",
            ("health_stale_after_minutes",),
            load_telegram_config,
            "health_stale_after_minutes",
        ),
        (
            "configs/risk/alpha_v1.yml",
            "risk",
            ("max_portfolio_exposure",),
            load_risk_config,
            "max_portfolio_exposure",
        ),
        (
            "configs/risk/alpha_v1.yml",
            "risk",
            ("max_leverage",),
            load_risk_config,
            "max_leverage",
        ),
        (
            "configs/risk/alpha_v1.yml",
            "risk",
            ("min_order_quantity",),
            load_risk_config,
            "min_order_quantity",
        ),
        (
            "configs/risk/alpha_v1.yml",
            "risk",
            ("min_order_notional",),
            load_risk_config,
            "min_order_notional",
        ),
        (
            "configs/risk/alpha_v1.yml",
            "risk",
            ("order_quantity_step",),
            load_risk_config,
            "order_quantity_step",
        ),
        (
            "configs/risk/alpha_v1.yml",
            "risk",
            ("liquidity_lookback_bars",),
            load_risk_config,
            "liquidity_lookback_bars",
        ),
        (
            "configs/risk/alpha_v1.yml",
            "risk",
            ("min_recent_quote_volume",),
            load_risk_config,
            "min_recent_quote_volume",
        ),
    ],
)
def test_missing_operational_fields_fail_loudly(
    tmp_path, source_path, top_key, field_path, loader, match
):
    cfg = yaml.safe_load(open(source_path))
    target = cfg[top_key]
    for key in field_path[:-1]:
        target = target[key]
    del target[field_path[-1]]

    path = write_yaml(tmp_path, cfg)

    with pytest.raises(ValidationError, match=match):
        loader(path)
