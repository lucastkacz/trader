"""YAML loaders for strict typed trader configuration."""

from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel

from src.engine.trader.config.models import (
    BacktestConfig,
    PipelineConfig,
    RiskConfig,
    StrategyConfig,
    TelegramConfig,
    UniverseConfig,
)

ConfigModel = TypeVar("ConfigModel", bound=BaseModel)


def _read_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")
    return data


def _load_config(path: str | Path, top_level_key: str, model: type[ConfigModel]) -> ConfigModel:
    data = _read_yaml(path)
    if top_level_key not in data:
        raise ValueError(f"Config file missing required top-level key '{top_level_key}': {path}")
    if len(data) != 1:
        keys = ", ".join(sorted(data))
        raise ValueError(f"Config file must contain only '{top_level_key}', found: {keys}")

    return model.model_validate(data[top_level_key])


def load_pipeline_config(path: str | Path) -> PipelineConfig:
    return _load_config(path, "pipeline", PipelineConfig)


def load_universe_config(path: str | Path) -> UniverseConfig:
    return _load_config(path, "universe", UniverseConfig)


def load_strategy_config(path: str | Path) -> StrategyConfig:
    return _load_config(path, "strategy", StrategyConfig)


def load_backtest_config(path: str | Path) -> BacktestConfig:
    return _load_config(path, "backtest", BacktestConfig)


def load_risk_config(path: str | Path) -> RiskConfig:
    return _load_config(path, "risk", RiskConfig)


def load_telegram_config(path: str | Path) -> TelegramConfig:
    return _load_config(path, "telegram", TelegramConfig)
