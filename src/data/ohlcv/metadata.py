"""Typed OHLCV metadata persisted with stored datasets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.data.ohlcv.frames import normalize_ohlcv_frame
from src.utils.timeframe_math import get_timeframe_minutes


@dataclass(frozen=True)
class OHLCVMarketMetadata:
    """Market contract context persisted with OHLCV datasets."""

    market_type: str | None = None
    market_sub_type: str | None = None
    settle: str | None = None


class OHLCVMetadata(BaseModel):
    """Typed metadata persisted with a stored OHLCV dataset."""

    model_config = ConfigDict(extra="ignore")

    schema_version: int = 2
    symbol: str
    exchange: str
    timeframe: str
    source: str
    market_type: str | None = None
    market_sub_type: str | None = None
    settle: str | None = None
    coverage_status: str
    quality_status: str = "UNCHECKED"
    total_candles: int = Field(ge=0)
    expected_candles: int | None = Field(default=None, ge=0)
    missing_candles: int | None = Field(default=None, ge=0)
    gap_count: int | None = Field(default=None, ge=0)
    max_gap_ms: int | None = Field(default=None, ge=0)
    first_ts: int | None = None
    last_ts: int | None = None
    coverage_start_ms: int | None = None
    coverage_end_ms: int | None = None
    last_closed_candle_ms: int | None = None
    updated_at: str | None = None

    @field_validator("symbol", "exchange", "timeframe", "source", "coverage_status")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("metadata text fields must be non-empty")
        return value

    @classmethod
    def from_frame(
        cls,
        *,
        symbol: str,
        exchange: str,
        timeframe: str,
        source: str,
        frame: pd.DataFrame,
        coverage_status: str | None = None,
        coverage_start_ms: int | None = None,
        coverage_end_ms: int | None = None,
        last_closed_candle_ms: int | None = None,
        quality_status: str | None = None,
        market_type: str | None = None,
        market_sub_type: str | None = None,
        settle: str | None = None,
    ) -> "OHLCVMetadata":
        """Build metadata from a normalized or normalizable OHLCV frame."""
        normalized = normalize_ohlcv_frame(frame)
        first_ts = None if normalized.empty else int(normalized["timestamp"].min())
        last_ts = None if normalized.empty else int(normalized["timestamp"].max())
        coverage_start = coverage_start_ms if coverage_start_ms is not None else first_ts
        coverage_end = coverage_end_ms if coverage_end_ms is not None else last_ts
        quality = _inspect_quality(
            frame=normalized,
            timeframe=timeframe,
            coverage_start_ms=coverage_start,
            coverage_end_ms=coverage_end,
        )
        return cls(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            source=source,
            market_type=market_type,
            market_sub_type=market_sub_type,
            settle=settle,
            coverage_status=coverage_status
            or _coverage_status(last_ts=last_ts, coverage_end_ms=coverage_end),
            quality_status=quality_status or quality["quality_status"],
            total_candles=len(normalized),
            expected_candles=quality["expected_candles"],
            missing_candles=quality["missing_candles"],
            gap_count=quality["gap_count"],
            max_gap_ms=quality["max_gap_ms"],
            first_ts=first_ts,
            last_ts=last_ts,
            coverage_start_ms=coverage_start,
            coverage_end_ms=coverage_end,
            last_closed_candle_ms=last_closed_candle_ms,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

    @classmethod
    def from_mapping(
        cls,
        metadata: Mapping[str, object],
        *,
        symbol: str,
        exchange: str,
        timeframe: str,
    ) -> "OHLCVMetadata":
        """Parse persisted metadata, filling legacy files with path context."""
        data = dict(metadata)
        data.setdefault("symbol", symbol)
        data.setdefault("exchange", exchange)
        data.setdefault("timeframe", timeframe)
        data.setdefault("source", data.get("source") or exchange)
        data.setdefault("coverage_status", data.get("status") or "UNKNOWN")
        data.setdefault("schema_version", 1)
        data.setdefault("quality_status", data.get("quality_status") or "UNCHECKED")
        if "row_count" in data and "total_candles" not in data:
            data["total_candles"] = data["row_count"]
        data.setdefault("total_candles", 0)
        return cls.model_validate(data)

    def to_parquet_metadata(self) -> dict[str, str]:
        """Return a string-only metadata map compatible with PyArrow."""
        dumped = self.model_dump(exclude_none=True)
        return {key: str(value) for key, value in dumped.items()}


def _coverage_status(*, last_ts: int | None, coverage_end_ms: int | None) -> str:
    if last_ts is None:
        return "NO_DATA"
    if coverage_end_ms is not None and last_ts < coverage_end_ms:
        return "INCOMPLETE"
    return "COMPLETE"


def _inspect_quality(
    *,
    frame: pd.DataFrame,
    timeframe: str,
    coverage_start_ms: int | None,
    coverage_end_ms: int | None,
) -> dict[str, int | str | None]:
    if frame.empty or coverage_start_ms is None or coverage_end_ms is None:
        return {
            "quality_status": "UNCHECKED",
            "expected_candles": None,
            "missing_candles": None,
            "gap_count": None,
            "max_gap_ms": None,
        }

    bar_ms = int(get_timeframe_minutes(timeframe) * 60_000)
    timestamps = frame["timestamp"].sort_values().astype("int64").tolist()
    expected_candles = max(0, ((coverage_end_ms - coverage_start_ms) // bar_ms) + 1)
    missing_candles = max(expected_candles - len(set(timestamps)), 0)
    has_unexpected_interval = any(
        current - previous < bar_ms
        for previous, current in zip(timestamps, timestamps[1:])
    )
    gaps = _gap_durations_ms(
        timestamps=timestamps,
        coverage_start_ms=coverage_start_ms,
        coverage_end_ms=coverage_end_ms,
        bar_ms=bar_ms,
    )
    gap_count = len(gaps)
    max_gap_ms = max(gaps) if gaps else 0
    quality_status = "VALIDATED"
    if has_unexpected_interval:
        quality_status = "INVALID"
    elif missing_candles > 0 or gap_count > 0:
        quality_status = "HAS_GAPS"
    return {
        "quality_status": quality_status,
        "expected_candles": expected_candles,
        "missing_candles": missing_candles,
        "gap_count": gap_count,
        "max_gap_ms": max_gap_ms,
    }


def _gap_durations_ms(
    *,
    timestamps: list[int],
    coverage_start_ms: int,
    coverage_end_ms: int,
    bar_ms: int,
) -> list[int]:
    gaps = []
    first_ts = timestamps[0]
    last_ts = timestamps[-1]
    if first_ts > coverage_start_ms:
        gaps.append(first_ts - coverage_start_ms)
    for previous, current in zip(timestamps, timestamps[1:]):
        missing_duration = current - previous - bar_ms
        if missing_duration > 0:
            gaps.append(missing_duration)
    if last_ts < coverage_end_ms:
        gaps.append(coverage_end_ms - last_ts)
    return gaps
