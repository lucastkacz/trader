"""Historical OHLCV backfill service."""

from __future__ import annotations

import asyncio

import pandas as pd

from src.data.ohlcv import (
    OHLCVMetadata,
    apply_ohlcv_retention,
    empty_ohlcv_frame,
    merge_ohlcv_frames,
    normalize_ohlcv_frame,
)
from src.data.sync.helpers import (
    aggregate_sync_results,
    coverage_status,
    int_or_none,
    metadata_covers_window,
    symbol_result,
)
from src.data.sync.models import (
    MarketDataAdapter,
    OHLCVBackfillRequest,
    OHLCVFetchPolicy,
    OHLCVStore,
    OHLCVSymbolSyncResult,
    OHLCVSyncResult,
    Sleep,
)
from src.universe.filters.market_tickers import select_symbols_by_quote_volume


class OHLCVBackfillService:
    """Download and persist historical OHLCV windows."""

    def __init__(
        self,
        *,
        market_data: MarketDataAdapter,
        store: OHLCVStore,
        policy: OHLCVFetchPolicy,
        sleep: Sleep | None = None,
    ) -> None:
        self.market_data = market_data
        self.store = store
        self.policy = policy
        self.sleep = sleep or asyncio.sleep

    async def run(self, request: OHLCVBackfillRequest) -> OHLCVSyncResult:
        """Backfill all requested or universe-discovered symbols."""
        if request.symbols is not None:
            symbols = list(request.symbols)
        else:
            tickers = await self.market_data.fetch_market_tickers()
            symbols = select_symbols_by_quote_volume(
                tickers,
                min_quote_volume=request.min_volume,
            )
        if request.limit_symbols is not None:
            symbols = symbols[: request.limit_symbols]

        results = []
        for symbol in symbols:
            results.append(await self.backfill_symbol(request, symbol))
        return aggregate_sync_results(request.exchange_id, request.timeframe, results)

    async def backfill_symbol(
        self,
        request: OHLCVBackfillRequest,
        symbol: str,
    ) -> OHLCVSymbolSyncResult:
        """Backfill a single symbol for the requested historical window."""
        metadata = self.store.read_metadata(symbol, request.timeframe, request.exchange_id)
        if metadata_covers_window(metadata, request.start_ts, request.end_ts):
            return OHLCVSymbolSyncResult(
                symbol=symbol,
                status="SKIPPED_COMPLETE",
                fetched_bars=0,
                saved_bars=int_or_none(metadata.get("total_candles")) or 0,
                first_ts=int_or_none(metadata.get("first_ts")),
                last_ts=int_or_none(metadata.get("last_ts")),
                notes=("metadata_covers_requested_window",),
            )

        try:
            fetched = await self.fetch_window(
                symbol=symbol,
                timeframe=request.timeframe,
                since_ts=request.start_ts,
                end_ts=request.end_ts,
            )
        except Exception as exc:
            return OHLCVSymbolSyncResult(
                symbol=symbol,
                status="FAILED",
                fetched_bars=0,
                saved_bars=0,
                first_ts=None,
                last_ts=None,
                notes=(f"{type(exc).__name__}: {exc}",),
            )

        if fetched.empty:
            return OHLCVSymbolSyncResult(
                symbol=symbol,
                status="NO_DATA",
                fetched_bars=0,
                saved_bars=0,
                first_ts=None,
                last_ts=None,
                notes=("exchange_returned_no_rows",),
            )

        retained = apply_ohlcv_retention(fetched, request.retention_policy)
        status = coverage_status(retained, request.end_ts)
        metadata_model = OHLCVMetadata.from_frame(
            symbol=symbol,
            exchange=request.exchange_id,
            timeframe=request.timeframe,
            source=request.exchange_id,
            frame=retained,
            coverage_status=status,
            coverage_start_ms=request.start_ts,
            coverage_end_ms=request.end_ts,
            last_closed_candle_ms=request.end_ts,
            market_type=request.market.market_type,
            market_sub_type=request.market.market_sub_type,
            settle=request.market.settle,
        )
        self.store.save_ohlcv(
            symbol,
            request.timeframe,
            retained,
            metadata_model,
            exchange=request.exchange_id,
        )
        return symbol_result(symbol, status, fetched_bars=len(fetched), saved=retained)

    async def fetch_window(
        self,
        *,
        symbol: str,
        timeframe: str,
        since_ts: int,
        end_ts: int,
    ) -> pd.DataFrame:
        """Fetch and merge a paginated OHLCV window."""
        frames = []
        current_since = since_ts
        while current_since <= end_ts:
            frame = await self._fetch_with_retries(
                symbol=symbol,
                timeframe=timeframe,
                since=current_since,
                end_ts=end_ts,
            )
            normalized = normalize_ohlcv_frame(frame)
            if normalized.empty:
                break
            frames.append(normalized)
            latest_ts = int(normalized["timestamp"].max())
            if latest_ts < current_since:
                break
            current_since = latest_ts + 1
            await self.sleep(self.policy.request_pause_seconds)
        if not frames:
            return empty_ohlcv_frame()
        return merge_ohlcv_frames(empty_ohlcv_frame(), pd.concat(frames))

    async def _fetch_with_retries(
        self,
        *,
        symbol: str,
        timeframe: str,
        since: int,
        end_ts: int,
    ) -> pd.DataFrame:
        attempts = self.policy.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                return await self.market_data.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=self.policy.fetch_limit,
                    since=since,
                    end_ts=end_ts,
                )
            except Exception:
                if attempt >= attempts:
                    raise
                await self.sleep(self.policy.backoff_seconds_after(attempt))
        raise AssertionError("OHLCV fetch retry loop exhausted")
