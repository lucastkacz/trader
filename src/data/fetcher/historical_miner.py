"""
Historical Miner
==================
Batch data ingestion orchestrator. Downloads complete OHLCV history for every
symbol in the exchange's universe via paginated API calls, deduplicates, and
saves to Parquet. This is the first step in the research pipeline.

Uses the unified exchange_client module — fully exchange-agnostic.

ARCHITECTURAL RULE: No default values for config-driven parameters.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pandas as pd
import ccxt.async_support as ccxt
from typing import Optional

from src.core.logger import logger, LogContext
from src.data.fetcher.exchange_client import create_exchange, fetch_universe, fetch_klines
from src.data.storage.local_parquet import ParquetStorage


class HistoricalMiner:
    def __init__(self, storage: ParquetStorage):
        self.storage = storage

    async def mine_symbol(
        self,
        exchange: ccxt.Exchange,
        exchange_id: str,
        symbol: str,
        start_ts: int,
        end_ts: int,
        timeframe: str,
    ) -> bool:
        """
        Downloads paginated history for a single symbol and validates completion.
        """
        ctx = LogContext(pair=symbol)

        metadata = self.storage.read_metadata(symbol, timeframe, exchange=exchange_id)
        if metadata.get("status") == "COMPLETE":
            logger.bind(**ctx.model_dump(exclude_none=True)).info(
                f"Skipping {symbol}: Already marked COMPLETE"
            )
            return True

        logger.bind(**ctx.model_dump(exclude_none=True)).info(
            f"Starting pipeline for {symbol}"
        )

        all_dfs = []
        current_since = start_ts
        retries = 0
        max_retries = 3

        while current_since < end_ts:
            try:
                df = await fetch_klines(
                    exchange=exchange,
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=1000,
                    since=current_since,
                    end_ts=end_ts,
                )

                if df.empty:
                    logger.bind(**ctx.model_dump(exclude_none=True)).warning(
                        "No more data returned from API. Halting pagination."
                    )
                    break

                all_dfs.append(df)

                last_ts = int(df.iloc[-1]["timestamp"])
                if last_ts == current_since:
                    break
                current_since = last_ts + 1

                retries = 0
                await asyncio.sleep(0.5)

            except (ccxt.NetworkError, RuntimeError) as e:
                retries += 1
                if retries > max_retries:
                    logger.bind(**ctx.model_dump(exclude_none=True)).error(
                        f"Max retries exceeded for {symbol}. Skipping."
                    )
                    return False

                backoff = 5 * (2 ** (retries - 1))
                logger.bind(**ctx.model_dump(exclude_none=True)).warning(
                    f"Network error on {symbol}. Backing off for {backoff}s. Error: {e}"
                )
                await asyncio.sleep(backoff)

        if not all_dfs:
            logger.bind(**ctx.model_dump(exclude_none=True)).warning(
                f"No history found at all for {symbol}."
            )
            return False

        final_df = pd.concat(all_dfs, ignore_index=True)
        final_df.drop_duplicates(subset=["timestamp"], inplace=True)
        final_df.sort_values("timestamp", inplace=True)

        custom_meta = {
            "source": exchange_id,
            "timeframe": timeframe,
            "status": "COMPLETE",
            "total_candles": str(len(final_df)),
            "first_ts": str(int(final_df.iloc[0]["timestamp"])),
            "last_ts": str(int(final_df.iloc[-1]["timestamp"])),
        }

        self.storage.save_ohlcv(
            symbol, timeframe, final_df, custom_meta, exchange=exchange_id
        )
        logger.bind(**ctx.model_dump(exclude_none=True)).info(
            f"Fully mined {symbol}. Saved {len(final_df)} candles to Parquet."
        )
        return True

    async def run(
        self,
        exchange_id: str,
        api_key: str,
        api_secret: str,
        timeframe: str,
        historical_days: int,
        min_volume: float,
        limit_symbols: Optional[int] = None,
    ):
        """
        Orchestrates full universe ingestion.

        Parameters
        ----------
        exchange_id : str — raw CCXT exchange ID
        api_key : str — API credential
        api_secret : str — API credential
        timeframe : str — candle interval
        historical_days : int — lookback window in days
        min_volume : float — minimum 24h quote volume for universe filter
        limit_symbols : int, optional — cap the universe size (test mode)
        """
        logger.info("Initializing Data Mine Orchestrator...")

        exchange = create_exchange(exchange_id, api_key, api_secret)
        try:
            universe = await fetch_universe(exchange, min_volume)
        finally:
            await exchange.close()

        if limit_symbols is not None:
            universe = universe[:limit_symbols]
            logger.warning(
                f"TEST MODE: Limited universe to {limit_symbols} symbols: {universe}"
            )

        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=historical_days)
        start_ts = int(start_dt.timestamp() * 1000)
        end_ts = int(end_dt.timestamp() * 1000)

        logger.info(
            f"Target Time Window: {start_dt.date()} to {end_dt.date()} "
            f"({historical_days} days)"
        )

        success_count = 0
        fail_count = 0

        for symbol in universe:
            # Create a fresh exchange instance per symbol to avoid stale connections
            sym_exchange = create_exchange(exchange_id, api_key, api_secret)
            try:
                ok = await self.mine_symbol(
                    exchange=sym_exchange,
                    exchange_id=exchange_id,
                    symbol=symbol,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    timeframe=timeframe,
                )
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
            finally:
                await sym_exchange.close()

        logger.info(
            f"MINING COMPLETE. Success: {success_count} | Failures: {fail_count}"
        )
        return success_count > 0
