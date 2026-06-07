"""Models and protocols for OHLCV sync services."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd

from src.data.ohlcv import OHLCVMarketMetadata, OHLCVMetadata, OHLCVRetentionPolicy

Sleep = Callable[[float], Awaitable[None]]


class OHLCVStore(Protocol):
    """Storage seam for local or remote OHLCV datasets."""

    def read_metadata(self, symbol: str, timeframe: str, exchange: str) -> dict[str, str]:
        """Read persisted metadata without loading the full OHLCV payload."""

    def load_ohlcv(self, symbol: str, timeframe: str, exchange: str) -> pd.DataFrame:
        """Load a stored OHLCV dataset."""

    def save_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        custom_metadata: dict[str, str] | OHLCVMetadata,
        exchange: str,
    ) -> None:
        """Replace a stored OHLCV dataset."""


class MarketDataAdapter(Protocol):
    """Read-only market-data seam used by OHLCV sync services."""

    async def fetch_universe(self, min_volume: float) -> list[str]:
        """Fetch tradable symbols above a quote-volume floor."""

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        *,
        since: int | None = None,
        end_ts: int | None = None,
    ) -> pd.DataFrame:
        """Fetch one OHLCV window."""


@dataclass(frozen=True)
class OHLCVFetchPolicy:
    """Retry and pacing policy for read-only OHLCV requests."""

    fetch_limit: int
    max_retries: int
    retry_backoff_seconds: float
    request_pause_seconds: float

    def __post_init__(self) -> None:
        if self.fetch_limit <= 0:
            raise ValueError("fetch_limit must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must be non-negative")
        if self.request_pause_seconds < 0:
            raise ValueError("request_pause_seconds must be non-negative")

    def backoff_seconds_after(self, failed_attempt: int) -> float:
        """Return exponential retry delay after a one-based failed attempt."""
        return self.retry_backoff_seconds * (2 ** (failed_attempt - 1))


@dataclass(frozen=True)
class OHLCVBackfillRequest:
    """Operator request for historical OHLCV ingestion."""

    exchange_id: str
    timeframe: str
    start_ts: int
    end_ts: int
    min_volume: float
    symbols: Sequence[str] | None = None
    limit_symbols: int | None = None
    retention_policy: OHLCVRetentionPolicy | None = None
    market: OHLCVMarketMetadata = field(default_factory=OHLCVMarketMetadata)

    def __post_init__(self) -> None:
        if self.start_ts >= self.end_ts:
            raise ValueError("start_ts must be earlier than end_ts")
        if self.min_volume < 0:
            raise ValueError("min_volume must be non-negative")
        if self.limit_symbols is not None and self.limit_symbols <= 0:
            raise ValueError("limit_symbols must be positive when provided")


@dataclass(frozen=True)
class OHLCVRefreshRequest:
    """Operator request for incremental OHLCV refresh."""

    exchange_id: str
    timeframe: str
    symbols: Sequence[str]
    end_ts: int
    overlap_bars: int
    missing_lookback_bars: int
    retention_policy: OHLCVRetentionPolicy | None = None
    market: OHLCVMarketMetadata = field(default_factory=OHLCVMarketMetadata)

    def __post_init__(self) -> None:
        if not self.symbols:
            raise ValueError("symbols must be non-empty")
        if self.end_ts < 0:
            raise ValueError("end_ts must be non-negative")
        if self.overlap_bars < 0:
            raise ValueError("overlap_bars must be non-negative")
        if self.missing_lookback_bars <= 0:
            raise ValueError("missing_lookback_bars must be positive")


@dataclass(frozen=True)
class OHLCVSymbolSyncResult:
    """Per-symbol outcome for an OHLCV sync operation."""

    symbol: str
    status: str
    fetched_bars: int
    saved_bars: int
    first_ts: int | None
    last_ts: int | None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class OHLCVSyncResult:
    """Aggregate outcome for a backfill or refresh run."""

    exchange_id: str
    timeframe: str
    symbol_count: int
    success_count: int
    failure_count: int
    results: tuple[OHLCVSymbolSyncResult, ...]
