"""Surviving-pair loading helpers for the trader runtime."""

import json
from pathlib import Path
from typing import Any

from src.core.logger import logger
from src.engine.trader.runtime.artifacts import (
    DEFAULT_PAIR_ARTIFACT_MAX_AGE_SECONDS,
    PAIR_ARTIFACT_CANDIDATE_FILENAME,
    PAIR_ARTIFACT_FILENAME,
    PAIR_ARTIFACT_PROMOTION_AUDIT_FILENAME,
    PAIR_ARTIFACT_SCHEMA_VERSION,
    PairArtifactEnvelope,
    PairArtifactMetadata,
    PairRefreshPromotionPolicy,
    SurvivingPairBestParams,
    SurvivingPairPerformance,
    SurvivingPairRow,
    ValidatedPairArtifact,
    build_pair_artifact,
    candidate_pair_artifact_path,
    extract_pair_artifact_pairs,
    pair_artifact_dir,
    promote_candidate_pair_artifact,
    promotion_audit_path,
    promoted_pair_artifact_path,
    validate_candidate_pair_artifact,
    validate_pair_artifact,
    validate_pair_artifact_file,
    validate_surviving_pair_rows,
    write_candidate_pair_artifact,
)


def load_tier1_pairs(
    timeframe: str,
    min_sharpe: float,
    exchange: str,
    artifact_base_dir: str | Path,
) -> list[dict[str, Any]]:
    """Load the promoted surviving pairs artifact and filter to Tier 1."""
    path = promoted_pair_artifact_path(timeframe, artifact_base_dir)
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
        pair for pair in all_pairs
        if pair["Performance"]["sharpe_ratio"] >= min_sharpe
    ]

    logger.info(
        f"Loaded {len(tier1)} Tier 1 pairs (Sharpe >= {min_sharpe}) "
        f"from {len(all_pairs)} total survivors."
    )
    return tier1


__all__ = [
    "DEFAULT_PAIR_ARTIFACT_MAX_AGE_SECONDS",
    "PAIR_ARTIFACT_CANDIDATE_FILENAME",
    "PAIR_ARTIFACT_FILENAME",
    "PAIR_ARTIFACT_PROMOTION_AUDIT_FILENAME",
    "PAIR_ARTIFACT_SCHEMA_VERSION",
    "PairArtifactEnvelope",
    "PairArtifactMetadata",
    "PairRefreshPromotionPolicy",
    "SurvivingPairBestParams",
    "SurvivingPairPerformance",
    "SurvivingPairRow",
    "ValidatedPairArtifact",
    "build_pair_artifact",
    "candidate_pair_artifact_path",
    "extract_pair_artifact_pairs",
    "load_tier1_pairs",
    "pair_artifact_dir",
    "promote_candidate_pair_artifact",
    "promotion_audit_path",
    "promoted_pair_artifact_path",
    "validate_candidate_pair_artifact",
    "validate_pair_artifact",
    "validate_pair_artifact_file",
    "validate_surviving_pair_rows",
    "write_candidate_pair_artifact",
]
