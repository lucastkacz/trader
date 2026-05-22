"""Artifact metadata helpers for pair-validity diagnostics."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.engine.trader.runtime.artifacts.promotion_audit import (
    PAIR_ARTIFACT_PROMOTION_AUDIT_FILENAME,
)
from src.engine.trader.runtime.pair_validity.time import parse_datetime


def load_latest_promoted_at(path: Path) -> datetime | None:
    """Return the latest promotion timestamp recorded for a promoted artifact."""
    audit_path = path.parent / PAIR_ARTIFACT_PROMOTION_AUDIT_FILENAME
    if not audit_path.exists():
        return None

    promoted_at = None
    with audit_path.open(encoding="utf-8") as f:
        for line in f:
            record = _parse_record(line)
            if record is None or record.get("event_type") != "pair_artifact_promoted":
                continue
            promoted = record.get("promoted")
            if not isinstance(promoted, dict):
                continue
            if Path(str(promoted.get("path"))).name != path.name:
                continue
            parsed = parse_datetime(record.get("promoted_at"))
            if parsed is not None:
                promoted_at = parsed
    return promoted_at


def research_window(pair: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    metadata = pair.get("Research_Window")
    if not isinstance(metadata, dict):
        return None, None
    return (
        parse_datetime(metadata.get("start")),
        parse_datetime(metadata.get("end")),
    )


def _parse_record(line: str) -> dict[str, Any] | None:
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return None
    return record if isinstance(record, dict) else None

