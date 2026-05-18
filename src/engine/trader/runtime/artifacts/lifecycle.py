"""Candidate and promoted eligible-pair artifact lifecycle helpers."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from src.engine.trader.runtime.artifacts.contract import (
    ValidatedPairArtifact,
    build_pair_artifact,
    validate_pair_artifact_file,
)
from src.engine.trader.runtime.artifacts.promotion_audit import (
    PAIR_ARTIFACT_PROMOTION_AUDIT_FILENAME,
    PairRefreshPromotionPolicy,
    append_promotion_audit_record,
    file_sha256,
)

PAIR_ARTIFACT_FILENAME = "surviving_pairs.json"
PAIR_ARTIFACT_CANDIDATE_FILENAME = "candidate_surviving_pairs.json"
DEFAULT_PAIR_ARTIFACT_MAX_AGE_SECONDS = 24 * 60 * 60


def pair_artifact_dir(
    timeframe: str,
    base_dir: str | Path,
) -> Path:
    """Return the universe artifact directory for a timeframe."""
    return Path(base_dir) / timeframe


def promoted_pair_artifact_path(
    timeframe: str,
    base_dir: str | Path,
) -> Path:
    """Return the execution-loaded promoted pair artifact path."""
    return pair_artifact_dir(timeframe, base_dir) / PAIR_ARTIFACT_FILENAME


def candidate_pair_artifact_path(
    timeframe: str,
    base_dir: str | Path,
) -> Path:
    """Return the research-written candidate pair artifact path."""
    return pair_artifact_dir(timeframe, base_dir) / PAIR_ARTIFACT_CANDIDATE_FILENAME


def promotion_audit_path(
    timeframe: str,
    base_dir: str | Path,
) -> Path:
    """Return the promotion audit log path for a timeframe."""
    return pair_artifact_dir(timeframe, base_dir) / PAIR_ARTIFACT_PROMOTION_AUDIT_FILENAME


def write_candidate_pair_artifact(
    pair_rows: list[dict[str, Any]],
    timeframe: str,
    exchange: str,
    base_dir: str | Path,
) -> Path:
    """Write a research candidate artifact without replacing execution's promoted artifact."""
    path = candidate_pair_artifact_path(timeframe, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    artifact = build_pair_artifact(
        pair_rows=pair_rows,
        timeframe=timeframe,
        exchange=exchange,
    )
    tmp_path.write_text(json.dumps(artifact, indent=4), encoding="utf-8")
    os.replace(tmp_path, path)
    return path


def validate_candidate_pair_artifact(
    timeframe: str,
    exchange: str,
    base_dir: str | Path,
    max_age_seconds: int = DEFAULT_PAIR_ARTIFACT_MAX_AGE_SECONDS,
    now: datetime | None = None,
) -> ValidatedPairArtifact:
    """Validate the research-written candidate artifact before promotion."""
    path = candidate_pair_artifact_path(timeframe, base_dir)
    if not path.exists():
        raise FileNotFoundError(
            f"Candidate surviving pairs artifact missing: {path}. "
            "Run research before promoting a new artifact."
        )
    return validate_pair_artifact_file(
        path=path,
        expected_timeframe=timeframe,
        expected_exchange=exchange,
        max_age_seconds=max_age_seconds,
        now=now,
    )


def promote_candidate_pair_artifact(
    timeframe: str,
    exchange: str,
    base_dir: str | Path,
    max_age_seconds: int = DEFAULT_PAIR_ARTIFACT_MAX_AGE_SECONDS,
    now: datetime | None = None,
    audit_path: str | Path | None = None,
    operator: str | None = None,
    pipeline_name: str | None = None,
    pair_refresh_policy: PairRefreshPromotionPolicy | None = None,
) -> Path:
    """Validate and atomically promote a candidate artifact for execution loading."""
    candidate_path = candidate_pair_artifact_path(timeframe, base_dir)
    promoted_path = promoted_pair_artifact_path(timeframe, base_dir)
    validated_candidate = validate_candidate_pair_artifact(
        timeframe=timeframe,
        exchange=exchange,
        base_dir=base_dir,
        max_age_seconds=max_age_seconds,
        now=now,
    )
    candidate_sha256 = file_sha256(candidate_path)
    promoted_at = now or datetime.now(validated_candidate.metadata.generated_at.tzinfo)
    promoted_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(candidate_path, promoted_path)
    if audit_path is not None:
        append_promotion_audit_record(
            audit_path=Path(audit_path),
            validated_candidate=validated_candidate,
            candidate_path=candidate_path,
            promoted_path=promoted_path,
            candidate_sha256=candidate_sha256,
            promoted_at=promoted_at,
            max_age_seconds=max_age_seconds,
            operator=operator,
            pipeline_name=pipeline_name,
            pair_refresh_policy=pair_refresh_policy,
        )
    return promoted_path
