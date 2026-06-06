"""Typed OHLCV metadata persisted with stored datasets."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.data.ohlcv.frames import normalize_ohlcv_frame


class OHLCVMetadata(BaseModel):
    """Typed metadata persisted with a stored OHLCV dataset."""

    model_config = ConfigDict(extra="ignore")

    schema_version: int = 1
    symbol: str
    exchange: str
    timeframe: str
    source: str
    status: str
    total_candles: int = Field(ge=0)
    first_ts: int | None = None
    last_ts: int | None = None
    coverage_start_ms: int | None = None
    coverage_end_ms: int | None = None
    last_closed_candle_ms: int | None = None
    quality_status: str = "VALIDATED"
    updated_at: str | None = None

    @field_validator("symbol", "exchange", "timeframe", "source", "status")
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
        status: str,
        frame: pd.DataFrame,
        coverage_start_ms: int | None = None,
        coverage_end_ms: int | None = None,
        last_closed_candle_ms: int | None = None,
        quality_status: str = "VALIDATED",
    ) -> "OHLCVMetadata":
        """Build metadata from a normalized or normalizable OHLCV frame."""
        normalized = normalize_ohlcv_frame(frame)
        first_ts = None if normalized.empty else int(normalized["timestamp"].min())
        last_ts = None if normalized.empty else int(normalized["timestamp"].max())
        return cls(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            source=source,
            status=status,
            total_candles=len(normalized),
            first_ts=first_ts,
            last_ts=last_ts,
            coverage_start_ms=coverage_start_ms
            if coverage_start_ms is not None
            else first_ts,
            coverage_end_ms=coverage_end_ms if coverage_end_ms is not None else last_ts,
            last_closed_candle_ms=last_closed_candle_ms,
            quality_status=quality_status,
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
        data.setdefault("status", data.get("status") or "UNKNOWN")
        data.setdefault("schema_version", 1)
        data.setdefault("quality_status", data.get("quality_status") or "UNKNOWN")
        if "row_count" in data and "total_candles" not in data:
            data["total_candles"] = data["row_count"]
        data.setdefault("total_candles", 0)
        return cls.model_validate(data)

    def to_parquet_metadata(self) -> dict[str, str]:
        """Return a string-only metadata map compatible with PyArrow."""
        dumped = self.model_dump(exclude_none=True)
        return {key: str(value) for key, value in dumped.items()}
