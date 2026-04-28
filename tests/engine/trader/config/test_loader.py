from copy import deepcopy

import pytest
import yaml
from pydantic import ValidationError

from src.engine.trader.config import (
    PipelineConfig,
    load_backtest_config,
    load_pipeline_config,
    load_risk_config,
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
    assert dev_pipeline.execution.order_execution.mode == "state_only"
    assert load_pipeline_config("configs/pipelines/uat.yml").execution.max_ticks is None
    assert load_pipeline_config("configs/pipelines/prod.yml").execution.max_ticks is None
    assert load_pipeline_config("configs/pipelines/ci_1m.yml").execution.max_ticks == 5
    assert load_pipeline_config("configs/pipelines/ci_4h.yml").execution.max_ticks == 1

    universe_cfg = load_universe_config("configs/universe/alpha_v1.yml")
    assert universe_cfg.filters.min_volume_liquidity == 20_000_000
    assert universe_cfg.cointegration.ewma_span_bars == 48
    assert load_strategy_config("configs/strategy/alpha_v1.yml").execution.volatility_lookback_bars == 60
    assert load_backtest_config("configs/backtest/stress_test.yml").friction.taker_fee == 0.0006
    assert load_risk_config("configs/risk/alpha_v1.yml").max_leverage == 10.0
    assert load_telegram_config("configs/telegram/dev.yml").environment == "DEV"
    assert load_telegram_config("configs/telegram/dev.yml").holding_period_bar_minutes == 1
    assert load_telegram_config("configs/telegram/uat.yml").environment == "UAT"
    assert load_telegram_config("configs/telegram/uat.yml").holding_period_bar_minutes == 240
    assert load_telegram_config("configs/telegram/prod.yml").environment == "PROD"
    assert load_telegram_config("configs/telegram/prod.yml").holding_period_bar_minutes == 240


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
            ("execution", "exchange"),
            load_pipeline_config,
            "exchange",
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
            "configs/strategy/alpha_v1.yml",
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
            "configs/risk/alpha_v1.yml",
            "risk",
            ("max_leverage",),
            load_risk_config,
            "max_leverage",
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


def test_wrong_top_level_key_fails_before_validation(tmp_path):
    path = write_yaml(tmp_path, {"strategy": {"name": "wrong"}})

    with pytest.raises(ValueError, match="top-level key 'pipeline'"):
        load_pipeline_config(path)


def test_extra_config_keys_are_rejected(tmp_path):
    cfg = yaml.safe_load(open("configs/pipelines/dev.yml"))
    cfg["pipeline"]["execution"]["implicit_default"] = 123
    path = write_yaml(tmp_path, cfg)

    with pytest.raises(ValidationError, match="implicit_default"):
        load_pipeline_config(path)
