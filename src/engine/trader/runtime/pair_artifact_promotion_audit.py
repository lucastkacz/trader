"""Audit records for eligible-pair artifact promotion."""

import json
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from src.engine.trader.runtime.pair_artifact_contract import ValidatedPairArtifact

PAIR_ARTIFACT_PROMOTION_AUDIT_FILENAME = "promotion_audit.jsonl"


@dataclass(frozen=True)
class PairRefreshPromotionPolicy:
    """Pair refresh policy recorded with promotion audit events."""

    mode: str
    reload_policy: str
    stale_open_position_policy: str


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_promotion_audit_record(
    audit_path: Path,
    validated_candidate: ValidatedPairArtifact,
    candidate_path: Path,
    promoted_path: Path,
    candidate_sha256: str,
    promoted_at: datetime,
    max_age_seconds: int,
    operator: str | None,
    pipeline_name: str | None,
    pair_refresh_policy: PairRefreshPromotionPolicy | None,
) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                _build_promotion_audit_record(
                    validated_candidate=validated_candidate,
                    candidate_path=candidate_path,
                    promoted_path=promoted_path,
                    candidate_sha256=candidate_sha256,
                    promoted_at=promoted_at,
                    max_age_seconds=max_age_seconds,
                    operator=operator,
                    pipeline_name=pipeline_name,
                    pair_refresh_policy=pair_refresh_policy,
                ),
                sort_keys=True,
            )
        )
        f.write("\n")


def _build_promotion_audit_record(
    validated_candidate: ValidatedPairArtifact,
    candidate_path: Path,
    promoted_path: Path,
    candidate_sha256: str,
    promoted_at: datetime,
    max_age_seconds: int,
    operator: str | None,
    pipeline_name: str | None,
    pair_refresh_policy: PairRefreshPromotionPolicy | None,
) -> dict[str, Any]:
    metadata = validated_candidate.metadata
    record: dict[str, Any] = {
        "schema_version": 1,
        "event_type": "pair_artifact_promoted",
        "promoted_at": promoted_at.isoformat(),
        "operator": operator,
        "pipeline_name": pipeline_name,
        "timeframe": metadata.timeframe,
        "exchange": metadata.exchange,
        "candidate": {
            "path": str(candidate_path),
            "sha256": candidate_sha256,
            "schema_version": metadata.schema_version,
            "artifact_type": metadata.artifact_type,
            "generated_at": metadata.generated_at.isoformat(),
            "timeframe": metadata.timeframe,
            "exchange": metadata.exchange,
            "pair_count": metadata.pair_count,
        },
        "promoted": {
            "path": str(promoted_path),
            "sha256": candidate_sha256,
        },
        "validation": {"max_age_seconds": max_age_seconds},
    }
    if pair_refresh_policy is not None:
        record["pair_refresh"] = {
            "mode": pair_refresh_policy.mode,
            "reload_policy": pair_refresh_policy.reload_policy,
            "stale_open_position_policy": (
                pair_refresh_policy.stale_open_position_policy
            ),
        }
    return record
