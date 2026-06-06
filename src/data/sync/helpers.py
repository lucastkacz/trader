"""Shared helpers for OHLCV sync services."""

from __future__ import annotations

import pandas as pd

from src.data.ohlcv import empty_ohlcv_frame, normalize_ohlcv_frame
from src.data.sync.models import OHLCVStore, OHLCVSymbolSyncResult, OHLCVSyncResult


def aggregate_sync_results(
    exchange_id: str,
    timeframe: str,
    results: list[OHLCVSymbolSyncResult],
) -> OHLCVSyncResult:
    """Aggregate per-symbol results into one sync result."""
    success_count = sum(result.status not in {"FAILED", "NO_DATA"} for result in results)
    failure_count = len(results) - success_count
    return OHLCVSyncResult(
        exchange_id=exchange_id,
        timeframe=timeframe,
        symbol_count=len(results),
        success_count=success_count,
        failure_count=failure_count,
        results=tuple(results),
    )


def load_existing_ohlcv(
    store: OHLCVStore,
    symbol: str,
    timeframe: str,
    exchange_id: str,
) -> pd.DataFrame:
    """Load existing OHLCV data or return an empty canonical frame."""
    try:
        return normalize_ohlcv_frame(store.load_ohlcv(symbol, timeframe, exchange_id))
    except FileNotFoundError:
        return empty_ohlcv_frame()


def metadata_covers_window(
    metadata: dict[str, str],
    start_ts: int,
    end_ts: int,
) -> bool:
    """Return whether metadata claims coverage for a requested window."""
    first_ts = int_or_none(metadata.get("first_ts"))
    last_ts = int_or_none(metadata.get("last_ts"))
    if first_ts is None or last_ts is None:
        return False
    return first_ts <= start_ts and last_ts >= end_ts


def coverage_status(frame: pd.DataFrame, end_ts: int) -> str:
    """Return COMPLETE when a frame reaches the requested end timestamp."""
    latest_ts = latest_ts_or_none(frame)
    if latest_ts is None:
        return "NO_DATA"
    return "COMPLETE" if latest_ts >= end_ts else "INCOMPLETE"


def symbol_result(
    symbol: str,
    status: str,
    *,
    fetched_bars: int,
    saved: pd.DataFrame,
    notes: tuple[str, ...] = (),
) -> OHLCVSymbolSyncResult:
    """Build a per-symbol sync result from a saved frame."""
    return OHLCVSymbolSyncResult(
        symbol=symbol,
        status=status,
        fetched_bars=fetched_bars,
        saved_bars=len(saved),
        first_ts=first_ts_or_none(saved),
        last_ts=latest_ts_or_none(saved),
        notes=notes,
    )


def first_ts_or_none(frame: pd.DataFrame) -> int | None:
    """Return the first timestamp in an OHLCV frame."""
    if frame.empty:
        return None
    return int(frame["timestamp"].min())


def latest_ts_or_none(frame: pd.DataFrame) -> int | None:
    """Return the latest timestamp in an OHLCV frame."""
    if frame.empty:
        return None
    return int(frame["timestamp"].max())


def int_or_none(value: object | None) -> int | None:
    """Parse optional integer-like metadata values."""
    if value is None or value == "":
        return None
    return int(value)
