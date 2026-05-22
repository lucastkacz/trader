"""Validated eligible-pair artifact contract."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from src.engine.trader.runtime.artifacts.rows import validate_surviving_pair_rows

PAIR_ARTIFACT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ValidatedPairArtifact:
    """Validated pair artifact file ready for promotion or execution loading."""

    source_path: Path
    metadata: "PairArtifactMetadata"
    pairs: list[dict[str, Any]]


class PairArtifactMetadata(BaseModel):
    """Validated metadata for the research-to-execution pair artifact."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    artifact_type: Literal["surviving_pairs"]
    generated_at: datetime
    timeframe: str = Field(min_length=1)
    exchange: str = Field(min_length=1)
    pair_count: int = Field(ge=0)

    @field_validator("generated_at")
    @classmethod
    def generated_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("generated_at must include a timezone offset")
        return value


class PairArtifactEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: PairArtifactMetadata
    pairs: list[Any]


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


def validate_pair_artifact(
    artifact: Any,
    source_path: str | Path,
    expected_timeframe: str | None = None,
    expected_exchange: str | None = None,
    max_age_seconds: int | None = None,
    now: datetime | None = None,
) -> ValidatedPairArtifact:
    """Validate a surviving-pairs artifact envelope and return its typed contract."""
    envelope = _parse_pair_artifact_envelope(artifact, source_path)
    metadata = envelope.metadata
    _validate_metadata_scope(metadata, source_path, expected_timeframe, expected_exchange)
    if max_age_seconds is not None:
        _validate_artifact_freshness(metadata.generated_at, max_age_seconds, now, source_path)

    validated_pairs = validate_surviving_pair_rows(envelope.pairs, str(source_path))
    if metadata.pair_count != len(validated_pairs):
        raise ValueError(
            f"Surviving pairs artifact pair_count mismatch in {source_path}: "
            f"metadata={metadata.pair_count} actual={len(validated_pairs)}"
        )
    return ValidatedPairArtifact(Path(source_path), metadata, validated_pairs)


def _parse_pair_artifact_envelope(
    artifact: Any,
    source_path: str | Path,
) -> PairArtifactEnvelope:
    if isinstance(artifact, list):
        raise ValueError(
            f"Legacy list-only surviving pairs artifacts are not supported: {source_path}. "
            "Regenerate the artifact with metadata and pairs."
        )
    if not isinstance(artifact, dict):
        raise ValueError(
            f"Surviving pairs artifact must contain metadata and pairs: {source_path}"
        )

    try:
        return PairArtifactEnvelope.model_validate(artifact)
    except ValidationError as exc:
        raise ValueError(
            f"Malformed surviving pairs artifact envelope in {source_path}: {exc}"
        ) from exc


def _validate_metadata_scope(
    metadata: PairArtifactMetadata,
    source_path: str | Path,
    expected_timeframe: str | None,
    expected_exchange: str | None,
) -> None:
    if expected_timeframe is not None and metadata.timeframe != expected_timeframe:
        raise ValueError(
            f"Surviving pairs artifact timeframe mismatch in {source_path}: "
            f"expected {expected_timeframe}, found {metadata.timeframe}"
        )
    if expected_exchange is not None and metadata.exchange != expected_exchange:
        raise ValueError(
            f"Surviving pairs artifact exchange mismatch in {source_path}: "
            f"expected {expected_exchange}, found {metadata.exchange}"
        )


def _validate_artifact_freshness(
    generated_at: datetime,
    max_age_seconds: int,
    now: datetime | None,
    source_path: str | Path,
) -> None:
    if max_age_seconds < 0:
        raise ValueError("max_age_seconds must be non-negative")

    reference_time = now or datetime.now(timezone.utc)
    if (
        reference_time.tzinfo is None
        or reference_time.tzinfo.utcoffset(reference_time) is None
    ):
        raise ValueError("Artifact freshness reference time must include a timezone offset")

    age_seconds = (
        reference_time.astimezone(timezone.utc)
        - generated_at.astimezone(timezone.utc)
    ).total_seconds()
    if age_seconds < 0:
        raise ValueError(
            f"Surviving pairs artifact generated_at is in the future in {source_path}"
        )
    if age_seconds > max_age_seconds:
        raise ValueError(
            f"Surviving pairs artifact is stale in {source_path}: "
            f"age_seconds={int(age_seconds)} max_age_seconds={max_age_seconds}"
        )


def extract_pair_artifact_pairs(
    artifact: Any,
    source_path: str | Path,
    expected_timeframe: str | None = None,
    expected_exchange: str | None = None,
) -> list[dict[str, Any]]:
    """Validate a surviving-pairs artifact envelope and return its pair rows."""
    return validate_pair_artifact(
        artifact=artifact,
        source_path=source_path,
        expected_timeframe=expected_timeframe,
        expected_exchange=expected_exchange,
    ).pairs


def validate_pair_artifact_file(
    path: str | Path,
    expected_timeframe: str | None = None,
    expected_exchange: str | None = None,
    max_age_seconds: int | None = None,
    now: datetime | None = None,
) -> ValidatedPairArtifact:
    """Read and validate a surviving-pairs artifact file."""
    source_path = Path(path)
    with source_path.open() as f:
        return validate_pair_artifact(
            artifact=json.load(f),
            source_path=source_path,
            expected_timeframe=expected_timeframe,
            expected_exchange=expected_exchange,
            max_age_seconds=max_age_seconds,
            now=now,
        )
