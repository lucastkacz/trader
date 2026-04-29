"""Surviving-pair loading helpers for the trader runtime."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.core.logger import logger

PAIR_ARTIFACT_SCHEMA_VERSION = 1


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


def build_pair_artifact(
    pair_rows: list[dict[str, Any]],
    timeframe: str,
    exchange: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the canonical surviving-pairs artifact envelope."""
    return {
        "metadata": {
            "schema_version": PAIR_ARTIFACT_SCHEMA_VERSION,
            "artifact_type": "surviving_pairs",
            "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
            "timeframe": timeframe,
            "exchange": exchange,
            "pair_count": len(pair_rows),
        },
        "pairs": pair_rows,
    }


def extract_pair_artifact_pairs(
    artifact: Any,
    source_path: str | Path,
    expected_timeframe: str | None = None,
    expected_exchange: str | None = None,
) -> list[dict[str, Any]]:
    """Validate a surviving-pairs artifact envelope and return its pair rows."""
    if not isinstance(artifact, dict):
        raise ValueError(
            f"Surviving pairs artifact must contain metadata and pairs: {source_path}"
        )

    metadata = artifact.get("metadata")
    rows = artifact.get("pairs")
    if not isinstance(metadata, dict):
        raise ValueError(f"Surviving pairs artifact missing metadata: {source_path}")

    if metadata.get("schema_version") != PAIR_ARTIFACT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported surviving pairs schema_version in {source_path}")
    if metadata.get("artifact_type") != "surviving_pairs":
        raise ValueError(f"Unsupported artifact_type in {source_path}")
    if expected_timeframe is not None and metadata.get("timeframe") != expected_timeframe:
        raise ValueError(
            f"Surviving pairs artifact timeframe mismatch in {source_path}: "
            f"expected {expected_timeframe}, found {metadata.get('timeframe')}"
        )
    if expected_exchange is not None and metadata.get("exchange") != expected_exchange:
        raise ValueError(
            f"Surviving pairs artifact exchange mismatch in {source_path}: "
            f"expected {expected_exchange}, found {metadata.get('exchange')}"
        )

    validated = validate_surviving_pair_rows(rows, str(source_path))
    if metadata.get("pair_count") != len(validated):
        raise ValueError(
            f"Surviving pairs artifact pair_count mismatch in {source_path}: "
            f"metadata={metadata.get('pair_count')} actual={len(validated)}"
        )
    return validated


def load_tier1_pairs(timeframe: str, min_sharpe: float, exchange: str) -> list[dict[str, Any]]:
    """Load surviving pairs and filter to Tier 1 by Sharpe threshold."""
    path = Path(f"data/universes/{timeframe}/surviving_pairs.json")
    if not path.exists():
        raise FileNotFoundError(
            f"Surviving pairs artifact missing: {path}. "
            "Run research first for this timeframe before launching execute."
        )

    with path.open() as f:
        all_pairs = extract_pair_artifact_pairs(
            artifact=json.load(f),
            source_path=path,
            expected_timeframe=timeframe,
            expected_exchange=exchange,
        )

    tier1 = [
        p for p in all_pairs
        if p["Performance"]["sharpe_ratio"] >= min_sharpe
    ]

    logger.info(
        f"Loaded {len(tier1)} Tier 1 pairs (Sharpe >= {min_sharpe}) "
        f"from {len(all_pairs)} total survivors."
    )
    return tier1
