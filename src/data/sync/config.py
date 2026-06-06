"""Typed YAML config for OHLCV sync policies."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from src.data.sync.models import OHLCVFetchPolicy


class StrictDataConfigModel(BaseModel):
    """Base model that rejects unknown data config keys."""

    model_config = ConfigDict(extra="forbid")


class OHLCVBackfillConfig(StrictDataConfigModel):
    """Config-backed OHLCV backfill fetch policy."""

    fetch_limit: int = Field(gt=0)
    max_retries: int = Field(ge=0)
    retry_backoff_seconds: float = Field(ge=0)
    request_pause_seconds: float = Field(ge=0)

    def to_fetch_policy(self) -> OHLCVFetchPolicy:
        """Return the runtime OHLCV fetch policy."""
        return OHLCVFetchPolicy(
            fetch_limit=self.fetch_limit,
            max_retries=self.max_retries,
            retry_backoff_seconds=self.retry_backoff_seconds,
            request_pause_seconds=self.request_pause_seconds,
        )


def load_ohlcv_backfill_config(path: str | Path) -> OHLCVBackfillConfig:
    """Load a typed OHLCV backfill config from YAML."""
    data = _read_yaml(path)
    top_level_key = "ohlcv_backfill"
    if top_level_key not in data:
        raise ValueError(
            f"Config file missing required top-level key '{top_level_key}': {path}"
        )
    if len(data) != 1:
        keys = ", ".join(sorted(data))
        raise ValueError(f"Config file must contain only '{top_level_key}', found: {keys}")
    return OHLCVBackfillConfig.model_validate(data[top_level_key])


def _read_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")
    return data
