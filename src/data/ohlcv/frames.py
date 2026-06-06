"""Canonical OHLCV DataFrame contract helpers."""

from __future__ import annotations

import pandas as pd

OHLCV_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")


class OHLCVFrameError(ValueError):
    """Raised when a DataFrame cannot satisfy the OHLCV storage contract."""


def empty_ohlcv_frame() -> pd.DataFrame:
    """Return an empty DataFrame with canonical OHLCV columns."""
    return pd.DataFrame(columns=list(OHLCV_COLUMNS))


def normalize_ohlcv_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return an OHLCV DataFrame with canonical columns, types, and ordering."""
    _require_columns(frame)
    if frame.empty:
        return empty_ohlcv_frame()

    normalized = frame.loc[:, list(OHLCV_COLUMNS)].copy()
    normalized["timestamp"] = _timestamp_to_ms(normalized["timestamp"])
    for column in ("open", "high", "low", "close", "volume"):
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    normalized = normalized.dropna(subset=list(OHLCV_COLUMNS))
    if normalized.empty:
        return empty_ohlcv_frame()

    normalized = normalized.astype(
        {
            "timestamp": "int64",
            "open": "float64",
            "high": "float64",
            "low": "float64",
            "close": "float64",
            "volume": "float64",
        }
    )
    normalized = normalized.drop_duplicates(subset=["timestamp"], keep="last")
    return normalized.sort_values("timestamp").reset_index(drop=True)


def validate_ohlcv_frame(frame: pd.DataFrame) -> None:
    """Raise when a frame violates the canonical OHLCV contract."""
    _require_columns(frame)
    if frame.empty:
        return

    timestamp_ms = _timestamp_to_ms(frame["timestamp"])
    if timestamp_ms.isna().any():
        raise OHLCVFrameError("OHLCV frame contains duplicate, null, or invalid rows")
    if timestamp_ms.duplicated().any():
        raise OHLCVFrameError("OHLCV frame contains duplicate timestamps")
    if not timestamp_ms.is_monotonic_increasing:
        raise OHLCVFrameError("OHLCV timestamps must be sorted ascending")

    normalized = normalize_ohlcv_frame(frame)
    if len(normalized) != len(frame):
        raise OHLCVFrameError("OHLCV frame contains duplicate, null, or invalid rows")


def merge_ohlcv_frames(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    """Merge two OHLCV frames, keeping the latest row for duplicate timestamps."""
    frames = []
    if not existing.empty:
        frames.append(normalize_ohlcv_frame(existing))
    if not incoming.empty:
        frames.append(normalize_ohlcv_frame(incoming))
    if not frames:
        return empty_ohlcv_frame()
    return normalize_ohlcv_frame(pd.concat(frames, ignore_index=True))


def _require_columns(frame: pd.DataFrame) -> None:
    missing = [column for column in OHLCV_COLUMNS if column not in frame.columns]
    if missing:
        raise OHLCVFrameError(
            f"OHLCV frame missing required columns: {', '.join(missing)}"
        )


def _timestamp_to_ms(timestamp: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(timestamp):
        numeric = pd.to_numeric(timestamp, errors="coerce")
        max_abs = numeric.abs().max()
        if pd.isna(max_abs):
            return numeric
        unit = "ms" if float(max_abs) > 10_000_000_000 else "s"
        parsed = pd.to_datetime(numeric, unit=unit, utc=True, errors="coerce")
    else:
        parsed = pd.to_datetime(timestamp, utc=True, errors="coerce")
    parsed_ms = parsed.astype("datetime64[ms, UTC]").astype("int64")
    return parsed_ms.where(parsed.notna())
