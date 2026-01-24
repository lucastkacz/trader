import ccxt.async_support as ccxt
import asyncio
import pandas as pd
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
from typing import List, Optional, Union
from tqdm.asyncio import tqdm
from lib.utils.logger import setup_logger
from lib.data.storage import MarketDataDB

logger = setup_logger(__name__)

async def fetch_ohlcv_single(
    exchange: ccxt.Exchange,
    symbol: str,
    start_date: str,
    end_date: str,
    timeframe: str,
    db: MarketDataDB,
    write_lock: asyncio.Lock,
    pbar: Optional[tqdm] = None
) -> str:
    """
    Fetches OHLCV data for a single symbol.
    Uses a shared DB connection protected by an asyncio Lock for thread-safe writes.
    """
    try:
        # Parse dates
        since_ts = exchange.parse8601(f"{start_date}T00:00:00Z")
        end_ts = exchange.parse8601(f"{end_date}T00:00:00Z")
        
        if since_ts is None or end_ts is None:
            logger.error(f"Invalid dates for {symbol}")
            if pbar: pbar.update(1)
            return "failed"

        # --- Incremental Fetch / Backfill Logic ---
        # We lock the read as well to ensure the connection isn't busy writing
        async with write_lock:
            last_ts_obj = db.get_last_timestamp(symbol, exchange.id, timeframe)
            first_ts_obj = db.get_first_timestamp(symbol, exchange.id, timeframe)
        
        if last_ts_obj and first_ts_obj:
            last_ts_ms = int(last_ts_obj.timestamp() * 1000)
            first_ts_ms = int(first_ts_obj.timestamp() * 1000)
            
            # Case 1: Pure Backfill (Requested range is completely BEFORE existing data)
            if end_ts < first_ts_ms:
                pass # Fetch normally
            
            # Case 2: Range is fully INSIDE existing coverage
            # We check if we actually have the data (Gap Detection)
            elif since_ts >= first_ts_ms and end_ts <= last_ts_ms:
                # Calculate expected rows (approximate for 1h/1d etc)
                duration_ms = end_ts - since_ts
                timeframe_ms = exchange.parse_timeframe(timeframe) * 1000
                expected_rows = (duration_ms // timeframe_ms) + 1
                
                # Check actual rows in DB
                async with write_lock:
                    actual_rows = db.count_rows(symbol, exchange.id, timeframe, since_ts, end_ts)
                
                # If we have >95% of data, we consider it up to date
                # This handles small missing candles (exchange downtime) without infinite refetching,
                # but ensures big gaps are filled.
                if actual_rows >= expected_rows * 0.95:
                    if pbar: pbar.update(1)
                    return "up_to_date"
                
                # If coverage is low, we fall through to FETCH (Gap Fill)
            
            # Case 3: Forward Update (Requested range extends BEYOND existing data)
            # We overlap slightly to ensure continuity, but mostly start from where we left off.
            elif since_ts < last_ts_ms and end_ts > last_ts_ms:
                since_ts = last_ts_ms
        
        all_ohlcv = []
        current_since = since_ts
        
        max_retries = 3
        
        # Parallel Network I/O (No Lock here)
        while current_since <= end_ts:
            fetched_segment = False
            for attempt in range(max_retries):
                try:
                    ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, current_since)
                    
                    if not ohlcv:
                        fetched_segment = True
                        break
                    
                    all_ohlcv.extend(ohlcv)
                    last_timestamp = ohlcv[-1][0]
                    current_since = last_timestamp + 1
                    fetched_segment = True
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 * (attempt + 1))
                    else:
                        logger.error(f"Failed to fetch {symbol}: {e}")
            
            if not fetched_segment:
                break
            if current_since >= end_ts: 
                break

        if pbar:
            pbar.update(1)

        # Process and Save
        if all_ohlcv:
            df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            
            df = df[df['timestamp'] <= pd.to_datetime(end_date).replace(tzinfo=timezone.utc)]
            
            # Check coverage
            expected_duration = (end_ts - since_ts) / 1000
            actual_start = df['timestamp'].min().timestamp()
            actual_end = df['timestamp'].max().timestamp()
            actual_duration = actual_end - actual_start
            
            # DEBUG: Print what we are about to save
            if "BTC" in symbol:
                logger.debug(f"[{symbol}] Dataframe Tail:\n{df.tail()}")

            # Serial Write (Protected by Lock)
            async with write_lock:
                db.save_ohlcv(df, symbol, exchange.id, timeframe)
            
            return "updated"
        
        return "failed"
        
    except Exception as e:
        logger.error(f"Unexpected error for {symbol}: {e}")
        return "failed"

async def fetch_all_ohlcv(
    symbols: List[str],
    start_date: str,
    end_date: str,
    db_path: Union[str, Path],
    timeframe: str = '1d',
    exchange_id: str = 'binance'
):
    """
    Fetches OHLCV data for multiple symbols in parallel.
    Uses a single database connection with a lock for serial writes.
    """
    db = MarketDataDB(db_path)
    write_lock = asyncio.Lock()
    
    exchange_class = getattr(ccxt, exchange_id)
    options = {'enableRateLimit': True}
    if exchange_id == 'binance':
        options['options'] = {'defaultType': 'future'}
        
    async with exchange_class(options) as exchange:
        logger.info(f"Starting parallel fetch for {len(symbols)} symbols from {exchange_id} ({timeframe})...")
        
        pbar = tqdm(total=len(symbols), desc="Fetching Assets")
        
        tasks = [
            fetch_ohlcv_single(exchange, symbol, start_date, end_date, timeframe, db, write_lock, pbar)
            for symbol in symbols
        ]
        
        results = await asyncio.gather(*tasks)
        pbar.close()
        
        # Summary
        counts = Counter(results)
        logger.info("=" * 40)
        logger.info(f"FETCH SUMMARY ({len(symbols)} Total)")
        logger.info("=" * 40)
        logger.info(f"✅ Up to date:        {counts['up_to_date']}")
        logger.info(f"📥 Updated/Fetched:   {counts['updated']}")
        logger.info(f"⏭️  Skipped (History): {counts['skipped_history']}")
        logger.info(f"❌ Failed:            {counts['failed']}")
        logger.info("=" * 40)
        
    db.close()

def run_fetch(symbols: List[str], start_date: str, end_date: str, db_path: Union[str, Path], **kwargs):
    """
    Synchronous wrapper to run the async fetcher.
    Auto-detects if a loop is already running (e.g. Jupyter) or if a new one is needed.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        try:
            import nest_asyncio
            nest_asyncio.apply()
            loop.run_until_complete(fetch_all_ohlcv(symbols, start_date, end_date, db_path=db_path, **kwargs))
        except ImportError:
             logger.warning("Running in an event loop (e.g., Jupyter) but 'nest_asyncio' is not installed.")
             loop.run_until_complete(fetch_all_ohlcv(symbols, start_date, end_date, db_path=db_path, **kwargs))
    else:
        asyncio.run(fetch_all_ohlcv(symbols, start_date, end_date, db_path=db_path, **kwargs))
