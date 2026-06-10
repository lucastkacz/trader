"""Typed YAML config for persisted market-data lifecycle policy."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from src.data.ohlcv import OHLCVRetentionPolicy


class StrictDataLifecycleConfigModel(BaseModel):
    """Base model that rejects unknown data lifecycle config keys."""

    model_config = ConfigDict(extra="forbid")


class DataRetentionConfig(StrictDataLifecycleConfigModel):
    """How long persisted market data may be kept after successful sync."""

    keep_days: int = Field(gt=0)
    prune_after_backfill: bool


class DataFreshnessConfig(StrictDataLifecycleConfigModel):
    """How stale local market data may be before it must be refreshed."""

    max_lag_minutes: int = Field(gt=0)
    on_stale: Literal["refresh", "fail", "ignore"]


class DataCleanupConfig(StrictDataLifecycleConfigModel):
    """How cleanup actions should be executed."""

    mode: Literal["dry_run", "delete"]
    delete_empty_symbol_dirs: bool


class DataLifecycleConfig(StrictDataLifecycleConfigModel):
    """Config-backed lifecycle policy for the active pipeline data store."""

    enabled: bool
    retention: DataRetentionConfig
    freshness: DataFreshnessConfig
    cleanup: DataCleanupConfig

    def retention_policy_after_backfill(self) -> OHLCVRetentionPolicy | None:
        """Return the OHLCV retention policy to apply after backfill."""
        if not self.enabled or not self.retention.prune_after_backfill:
            return None
        return OHLCVRetentionPolicy(max_age_days=self.retention.keep_days)


def load_data_lifecycle_config(path: str | Path) -> DataLifecycleConfig:
    """Load a typed data lifecycle config from YAML."""
    data = _read_yaml(path)
    top_level_key = "data_lifecycle"
    if top_level_key not in data:
        raise ValueError(
            f"Config file missing required top-level key '{top_level_key}': {path}"
        )
    if len(data) != 1:
        keys = ", ".join(sorted(data))
        raise ValueError(f"Config file must contain only '{top_level_key}', found: {keys}")
    return DataLifecycleConfig.model_validate(data[top_level_key])


def _read_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")
    return data
