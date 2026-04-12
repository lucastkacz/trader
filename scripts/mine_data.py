import asyncio
import argparse
from datetime import datetime, timedelta, timezone
import pandas as pd
import ccxt.async_support as ccxt

from src.core.logger import logger, LogContext
from src.data.fetcher.binance_client import fetch_usd_m_universe, fetch_klines
from src.data.storage.local_parquet import ParquetStorage

async def mine_symbol(symbol: str, storage: ParquetStorage, start_ts: int, end_ts: int, timeframe: str = "4h") -> bool:
    """
    Downloads paginated history and validates completion.
    """
    ctx = LogContext(pair=symbol)
    
    # 1. Checkpoint validation
    metadata = storage.read_metadata(symbol, timeframe, exchange="binanceusdm")
    if metadata.get("status") == "COMPLETE":
        logger.bind(**ctx.model_dump(exclude_none=True)).info(f"Skipping {symbol}: Already marked COMPLETE")
        return True

    logger.bind(**ctx.model_dump(exclude_none=True)).info(f"Starting pipeline for {symbol}")
    
    all_dfs = []
    current_since = start_ts
    retries = 0
    max_retries = 3
    
    while current_since < end_ts:
        try:
            df = await fetch_klines(symbol=symbol, timeframe=timeframe, limit=1000, since=current_since)
            
            if df.empty:
                logger.bind(**ctx.model_dump(exclude_none=True)).warning("No more data returned from API. Halting pagination.")
                break
                
            all_dfs.append(df)
            
            # Update current_since to the last timestamp + 1 millisecond to paginate exactly
            last_ts = int(df.iloc[-1]["timestamp"])
            if last_ts == current_since:
                 break
            current_since = last_ts + 1
            
            # Reset retries upon success
            retries = 0
            
            # Rate limiting sleep
            await asyncio.sleep(0.5)
            
        except (ccxt.NetworkError, RuntimeError) as e:
            retries += 1
            if retries > max_retries:
                logger.bind(**ctx.model_dump(exclude_none=True)).error(f"Max retries exceeded for {symbol}. Skipping.")
                return False
                
            backoff = 5 * (2 ** (retries - 1)) # 5s, 10s, 20s
            logger.bind(**ctx.model_dump(exclude_none=True)).warning(f"Network error on {symbol}. Backing off for {backoff}s. Error: {e}")
            await asyncio.sleep(backoff)
            
    if not all_dfs:
        logger.bind(**ctx.model_dump(exclude_none=True)).warning(f"No history found at all for {symbol}.")
        return False
        
    final_df = pd.concat(all_dfs, ignore_index=True)
    final_df.drop_duplicates(subset=["timestamp"], inplace=True)
    final_df.sort_values("timestamp", inplace=True)
    
    custom_meta = {
        "source": "binanceusdm",
        "timeframe": timeframe,
        "status": "COMPLETE",
        "total_candles": str(len(final_df)),
        "first_ts": str(int(final_df.iloc[0]["timestamp"])),
        "last_ts": str(int(final_df.iloc[-1]["timestamp"]))
    }
    
    storage.save_ohlcv(symbol, timeframe, final_df, custom_meta, exchange="binanceusdm")
    logger.bind(**ctx.model_dump(exclude_none=True)).info(f"Fully mined {symbol}. Saved {len(final_df)} candles to Parquet.")
    return True

async def main():
    parser = argparse.ArgumentParser(description="Epoch 1: Historical Alpha Discovery")
    parser.add_argument("--limit-symbols", type=int, default=None, help="Max number of coins to download (for testing)")
    parser.add_argument("--days", type=int, default=1460, help="Number of days to look back (default 1460 for 4 years)")
    args = parser.parse_args()

    storage = ParquetStorage()
    logger.info("Initializing Data Mine Orchestrator...")
    
    universe = await fetch_usd_m_universe()
    if args.limit_symbols:
        universe = universe[:args.limit_symbols]
        logger.warning(f"TEST MODE: Limited universe to {args.limit_symbols} symbols: {universe}")
        
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=args.days)
    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)
    
    logger.info(f"Target Time Window: {start_dt.date()} to {end_dt.date()} ({args.days} days)")
    
    success_count = 0
    fail_count = 0
    
    for symbol in universe:
        ok = await mine_symbol(symbol=symbol, storage=storage, start_ts=start_ts, end_ts=end_ts)
        if ok:
            success_count += 1
        else:
            fail_count += 1
            
    logger.info(f"MINING COMPLETE. Success: {success_count} | Failures: {fail_count}")

if __name__ == "__main__":
    asyncio.run(main())
