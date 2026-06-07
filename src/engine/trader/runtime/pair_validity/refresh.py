"""Read-only market-data refresh for promoted-pair diagnostics."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.data.ohlcv import OHLCVMarketMetadata
from src.data.storage.local_parquet import LocalOHLCVParquetStore
from src.engine.trader.runtime.pair_validity.market_data import normalize_ohlcv
from src.engine.trader.runtime.artifacts import validate_pair_artifact_file
from src.utils.timeframe_math import get_timeframe_minutes

FetchKlines = Callable[..., Awaitable[pd.DataFrame]]


@dataclass(frozen=True)
class PairDataRefreshPolicy:
    """Operator-supplied policy for refreshing local promoted-pair OHLCV."""

    overlap_bars: int
    missing_lookback_bars: int
    fetch_limit: int

    def __post_init__(self) -> None:
        if self.overlap_bars < 0:
            raise ValueError("overlap_bars must be non-negative")
        if self.missing_lookback_bars <= 0:
            raise ValueError("missing_lookback_bars must be positive")
        if self.fetch_limit <= 0:
            raise ValueError("fetch_limit must be positive")


@dataclass(frozen=True)
class SymbolRefreshResult:
    symbol: str
    status: str
    before_latest_at: str | None
    after_latest_at: str | None
    fetched_bars: int
    saved_bars: int
    since_ms: int
    end_ms: int
    notes: list[str]


@dataclass(frozen=True)
class PairDataRefreshReport:
    artifact_path: str
    timeframe: str
    exchange: str
    symbol_count: int
    started_at: str
    finished_at: str
    results: list[SymbolRefreshResult]


async def refresh_promoted_pair_market_data(
    *,
    surviving_pairs_path: str | Path,
    storage: LocalOHLCVParquetStore,
    exchange: Any,
    exchange_id: str,
    timeframe: str,
    policy: PairDataRefreshPolicy,
    fetch_klines: FetchKlines,
    market: OHLCVMarketMetadata | None = None,
    now: datetime | None = None,
) -> PairDataRefreshReport:
    """Fetch and append recent OHLCV for all symbols in the promoted artifact."""
    started_at = _utc_now()
    reference_time = _as_utc(now or started_at)
    end_ms = _closed_candle_end_ms(reference_time, timeframe)
    artifact = validate_pair_artifact_file(
        surviving_pairs_path,
        expected_timeframe=timeframe,
        expected_exchange=exchange_id,
    )
    symbols = sorted({
        symbol
        for pair in artifact.pairs
        for symbol in (pair["Asset_X"], pair["Asset_Y"])
    })

    results = []
    for symbol in symbols:
        results.append(
            await refresh_symbol_market_data(
                storage=storage,
                exchange=exchange,
                exchange_id=exchange_id,
                symbol=symbol,
                timeframe=timeframe,
                policy=policy,
                fetch_klines=fetch_klines,
                market=market,
                end_ms=end_ms,
            )
        )

    return PairDataRefreshReport(
        artifact_path=str(surviving_pairs_path),
        timeframe=timeframe,
        exchange=exchange_id,
        symbol_count=len(symbols),
        started_at=started_at.isoformat(),
        finished_at=_utc_now().isoformat(),
        results=results,
    )


async def refresh_symbol_market_data(
    *,
    storage: LocalOHLCVParquetStore,
    exchange: Any,
    exchange_id: str,
    symbol: str,
    timeframe: str,
    policy: PairDataRefreshPolicy,
    fetch_klines: FetchKlines,
    end_ms: int,
    market: OHLCVMarketMetadata | None = None,
) -> SymbolRefreshResult:
    """Append recent OHLCV for a single symbol without mutating exchange state."""
    existing = _load_existing_ohlcv(storage, symbol, timeframe, exchange_id)
    before_latest_ms = _latest_timestamp_ms(existing)
    since_ms = _refresh_since_ms(
        latest_ms=before_latest_ms,
        end_ms=end_ms,
        timeframe=timeframe,
        policy=policy,
    )
    notes: list[str] = []
    if since_ms > end_ms:
        return _result(
            symbol=symbol,
            status="UP_TO_DATE",
            before_latest_ms=before_latest_ms,
            after_latest_ms=before_latest_ms,
            fetched_bars=0,
            saved_bars=len(existing),
            since_ms=since_ms,
            end_ms=end_ms,
            notes=["local_data_already_beyond_closed_candle_end"],
        )

    fetched = await _fetch_window(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        policy=policy,
        fetch_klines=fetch_klines,
        since_ms=since_ms,
        end_ms=end_ms,
    )
    if fetched.empty:
        if before_latest_ms is not None and before_latest_ms < end_ms:
            notes.append("local_data_older_than_closed_candle_end")
        return _result(
            symbol=symbol,
            status="NO_NEW_DATA",
            before_latest_ms=before_latest_ms,
            after_latest_ms=before_latest_ms,
            fetched_bars=0,
            saved_bars=len(existing),
            since_ms=since_ms,
            end_ms=end_ms,
            notes=notes,
        )

    merged = _merge_ohlcv(existing, fetched)
    after_latest_ms = _latest_timestamp_ms(merged)
    refresh_status = "REFRESHED"
    if after_latest_ms is not None and after_latest_ms < end_ms:
        refresh_status = "INCOMPLETE"
        notes.append("local_data_older_than_closed_candle_end")
    metadata = _refresh_metadata(
        storage=storage,
        symbol=symbol,
        timeframe=timeframe,
        exchange_id=exchange_id,
        rows=len(merged),
        first_ms=int(merged["timestamp"].min()),
        refreshed_until_ms=int(merged["timestamp"].max()),
        refresh_status=refresh_status,
        policy=policy,
        market=market,
        end_ms=end_ms,
    )
    storage.save_ohlcv(symbol, timeframe, merged, metadata, exchange=exchange_id)
    return _result(
        symbol=symbol,
        status=refresh_status,
        before_latest_ms=before_latest_ms,
        after_latest_ms=after_latest_ms,
        fetched_bars=len(fetched),
        saved_bars=len(merged),
        since_ms=since_ms,
        end_ms=end_ms,
        notes=notes,
    )


async def _fetch_window(
    *,
    exchange: Any,
    symbol: str,
    timeframe: str,
    policy: PairDataRefreshPolicy,
    fetch_klines: FetchKlines,
    since_ms: int,
    end_ms: int,
) -> pd.DataFrame:
    frames = []
    current_since = since_ms
    while current_since <= end_ms:
        frame = await fetch_klines(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            limit=policy.fetch_limit,
            since=current_since,
            end_ts=end_ms,
        )
        normalized = _to_storage_ohlcv(frame)
        if normalized.empty:
            break
        frames.append(normalized)
        latest_ms = int(normalized["timestamp"].max())
        if latest_ms < current_since:
            break
        next_since = latest_ms + 1
        if next_since <= current_since:
            break
        current_since = next_since
    if not frames:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    return _merge_ohlcv(pd.DataFrame(), pd.concat(frames, ignore_index=True))


def _load_existing_ohlcv(
    storage: LocalOHLCVParquetStore,
    symbol: str,
    timeframe: str,
    exchange_id: str,
) -> pd.DataFrame:
    try:
        return _to_storage_ohlcv(storage.load_ohlcv(symbol, timeframe, exchange_id))
    except FileNotFoundError:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])


def _merge_ohlcv(existing: pd.DataFrame, fetched: pd.DataFrame) -> pd.DataFrame:
    merged = pd.concat([existing, fetched], ignore_index=True)
    if merged.empty:
        return merged
    merged = merged.dropna(subset=["timestamp"])
    merged = merged.drop_duplicates(subset=["timestamp"], keep="last")
    return merged.sort_values("timestamp").reset_index(drop=True)


def _to_storage_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    normalized = normalize_ohlcv(frame)
    output = normalized[["timestamp", "close"]].copy()
    for column in ["open", "high", "low", "volume"]:
        if column not in frame.columns:
            raise KeyError(f"OHLCV data must include {column} column")
        output[column] = pd.to_numeric(frame[column], errors="coerce")
    output["timestamp"] = normalized["timestamp"].map(
        lambda value: int(value.timestamp() * 1000)
    )
    columns = ["timestamp", "open", "high", "low", "close", "volume"]
    return output[columns].dropna().astype({"timestamp": "int64"})


def _refresh_since_ms(
    *,
    latest_ms: int | None,
    end_ms: int,
    timeframe: str,
    policy: PairDataRefreshPolicy,
) -> int:
    bar_ms = _bar_ms(timeframe)
    if latest_ms is None:
        return max(0, end_ms - (policy.missing_lookback_bars - 1) * bar_ms)
    overlap_ms = policy.overlap_bars * bar_ms
    return max(0, latest_ms - overlap_ms)


def _closed_candle_end_ms(now: datetime, timeframe: str) -> int:
    bar_ms = _bar_ms(timeframe)
    now_ms = int(_as_utc(now).timestamp() * 1000)
    return max(0, (now_ms // bar_ms) * bar_ms - bar_ms)


def _bar_ms(timeframe: str) -> int:
    return int(get_timeframe_minutes(timeframe) * 60 * 1000)


def _latest_timestamp_ms(frame: pd.DataFrame) -> int | None:
    if frame.empty:
        return None
    return int(frame["timestamp"].max())


def _refresh_metadata(
    *,
    storage: LocalOHLCVParquetStore,
    symbol: str,
    timeframe: str,
    exchange_id: str,
    rows: int,
    first_ms: int,
    refreshed_until_ms: int,
    refresh_status: str,
    policy: PairDataRefreshPolicy,
    market: OHLCVMarketMetadata | None,
    end_ms: int,
) -> dict[str, str]:
    existing = storage.read_metadata(symbol, timeframe, exchange=exchange_id)
    coverage_status = "INCOMPLETE" if refresh_status == "INCOMPLETE" else "COMPLETE"
    metadata = {
        **existing,
        "source": exchange_id,
        "timeframe": timeframe,
        "coverage_status": coverage_status,
        "refresh_status": refresh_status,
        "total_candles": str(rows),
        "coverage_start_ms": str(first_ms),
        "coverage_end_ms": str(end_ms),
        "last_closed_candle_ms": str(end_ms),
        "last_ts": str(refreshed_until_ms),
        "last_refresh_at": _utc_now().isoformat(),
        "refresh_overlap_bars": str(policy.overlap_bars),
    }
    if market is not None:
        if market.market_type is not None:
            metadata["market_type"] = market.market_type
        if market.market_sub_type is not None:
            metadata["market_sub_type"] = market.market_sub_type
        if market.settle is not None:
            metadata["settle"] = market.settle
    if "first_ts" not in metadata:
        metadata["first_ts"] = str(first_ms)
    return metadata


def _result(
    *,
    symbol: str,
    status: str,
    before_latest_ms: int | None,
    after_latest_ms: int | None,
    fetched_bars: int,
    saved_bars: int,
    since_ms: int,
    end_ms: int,
    notes: list[str],
) -> SymbolRefreshResult:
    return SymbolRefreshResult(
        symbol=symbol,
        status=status,
        before_latest_at=_format_ms(before_latest_ms),
        after_latest_at=_format_ms(after_latest_ms),
        fetched_bars=fetched_bars,
        saved_bars=saved_bars,
        since_ms=since_ms,
        end_ms=end_ms,
        notes=notes,
    )


def _format_ms(value: int | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
