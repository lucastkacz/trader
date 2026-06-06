"""Incremental OHLCV refresh service."""

from __future__ import annotations

from src.data.ohlcv import OHLCVMetadata, apply_ohlcv_retention, merge_ohlcv_frames
from src.data.sync.backfill import OHLCVBackfillService
from src.data.sync.helpers import (
    aggregate_sync_results,
    coverage_status,
    first_ts_or_none,
    latest_ts_or_none,
    load_existing_ohlcv,
    symbol_result,
)
from src.data.sync.models import (
    MarketDataAdapter,
    OHLCVFetchPolicy,
    OHLCVRefreshRequest,
    OHLCVStore,
    OHLCVSymbolSyncResult,
    OHLCVSyncResult,
    Sleep,
)
from src.utils.timeframe_math import get_timeframe_minutes


class OHLCVRefreshService:
    """Append missing recent OHLCV rows to existing stored datasets."""

    def __init__(
        self,
        *,
        market_data: MarketDataAdapter,
        store: OHLCVStore,
        policy: OHLCVFetchPolicy,
        sleep: Sleep | None = None,
    ) -> None:
        self.backfiller = OHLCVBackfillService(
            market_data=market_data,
            store=store,
            policy=policy,
            sleep=sleep,
        )
        self.store = store

    async def run(self, request: OHLCVRefreshRequest) -> OHLCVSyncResult:
        """Refresh all requested symbols up to the requested closed-candle end."""
        results = []
        for symbol in request.symbols:
            results.append(await self.refresh_symbol(request, symbol))
        return aggregate_sync_results(request.exchange_id, request.timeframe, results)

    async def refresh_symbol(
        self,
        request: OHLCVRefreshRequest,
        symbol: str,
    ) -> OHLCVSymbolSyncResult:
        """Refresh one symbol by fetching only the missing tail plus overlap."""
        try:
            existing = load_existing_ohlcv(
                self.store,
                symbol,
                request.timeframe,
                request.exchange_id,
            )
            latest_ts = latest_ts_or_none(existing)
            since_ts = _refresh_since_ts(
                latest_ts=latest_ts,
                end_ts=request.end_ts,
                timeframe=request.timeframe,
                overlap_bars=request.overlap_bars,
                missing_lookback_bars=request.missing_lookback_bars,
            )
            if since_ts > request.end_ts:
                return symbol_result(
                    symbol,
                    "UP_TO_DATE",
                    fetched_bars=0,
                    saved=existing,
                    notes=("local_data_already_covers_requested_end",),
                )

            fetched = await self.backfiller.fetch_window(
                symbol=symbol,
                timeframe=request.timeframe,
                since_ts=since_ts,
                end_ts=request.end_ts,
            )
            if fetched.empty:
                return symbol_result(
                    symbol,
                    "NO_NEW_DATA",
                    fetched_bars=0,
                    saved=existing,
                    notes=("exchange_returned_no_rows",),
                )

            merged = merge_ohlcv_frames(existing, fetched)
            retained = apply_ohlcv_retention(merged, request.retention_policy)
            status = coverage_status(retained, request.end_ts)
            metadata_model = OHLCVMetadata.from_frame(
                symbol=symbol,
                exchange=request.exchange_id,
                timeframe=request.timeframe,
                source=request.exchange_id,
                status=status,
                frame=retained,
                coverage_start_ms=first_ts_or_none(retained),
                coverage_end_ms=request.end_ts,
                last_closed_candle_ms=request.end_ts,
            )
            self.store.save_ohlcv(
                symbol,
                request.timeframe,
                retained,
                metadata_model,
                exchange=request.exchange_id,
            )
            return symbol_result(symbol, status, fetched_bars=len(fetched), saved=retained)
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


def _refresh_since_ts(
    *,
    latest_ts: int | None,
    end_ts: int,
    timeframe: str,
    overlap_bars: int,
    missing_lookback_bars: int,
) -> int:
    bar_ms = int(get_timeframe_minutes(timeframe) * 60 * 1000)
    if latest_ts is None:
        return max(0, end_ts - (missing_lookback_bars - 1) * bar_ms)
    return max(0, latest_ts - overlap_bars * bar_ms)
