"""Surviving-pair loading helpers for the trader runtime."""

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.core.logger import logger


class SurvivingPairBestParams(BaseModel):
    """Validated Best_Params block from surviving_pairs.json."""

    model_config = ConfigDict(extra="allow")

    lookback_bars: int
    entry_z: float


class SurvivingPairPerformance(BaseModel):
    """Validated Performance block from surviving_pairs.json."""

    model_config = ConfigDict(extra="allow")

    sharpe_ratio: float


class SurvivingPairRow(BaseModel):
    """Validated generated surviving pair row."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    asset_x: str = Field(alias="Asset_X")
    asset_y: str = Field(alias="Asset_Y")
    hedge_ratio: float = Field(alias="Hedge_Ratio")
    best_params: SurvivingPairBestParams = Field(alias="Best_Params")
    performance: SurvivingPairPerformance = Field(alias="Performance")


def validate_surviving_pair_rows(rows: Any, source_path: str) -> list[dict[str, Any]]:
    """Validate generated surviving pair rows and preserve their JSON shape."""
    if not isinstance(rows, list):
        raise ValueError(f"Surviving pairs artifact must contain a list: {source_path}")

    validated = []
    for index, row in enumerate(rows):
        try:
            parsed = SurvivingPairRow.model_validate(row)
        except ValidationError as exc:
            raise ValueError(
                f"Malformed surviving pair row {index} in {source_path}: {exc}"
            ) from exc
        validated.append(parsed.model_dump(by_alias=True))
    return validated


def load_tier1_pairs(timeframe: str, min_sharpe: float) -> list[dict[str, Any]]:
    """Load surviving pairs and filter to Tier 1 by Sharpe threshold."""
    path = f"data/universes/{timeframe}/surviving_pairs.json"
    with open(path) as f:
        all_pairs = validate_surviving_pair_rows(json.load(f), path)

    tier1 = [
        p for p in all_pairs
        if p["Performance"]["sharpe_ratio"] >= min_sharpe
    ]

    logger.info(
        f"Loaded {len(tier1)} Tier 1 pairs (Sharpe >= {min_sharpe}) "
        f"from {len(all_pairs)} total survivors."
    )
    return tier1
