import pytest
import asyncio
import time
from datetime import datetime, timezone
import pandas as pd

from src.exchange.data.ccxt_adapter import CcxtMarketDataAdapter
from src.exchange.config.venue import load_ccxt_exchange_config
from src.data.ohlcv.metadata import OHLCVMetadata

def _exchange_config():
    return load_ccxt_exchange_config("configs/exchange/market_profiles/linear_usdt_swap.yml")

async def _fetch_paginated_funding_rate_history(adapter, symbol, start_ms, end_ms):
    """Fetches funding rate history in a paginated loop to cover the full window."""
    all_dfs = []
    current_since = start_ms
    limit = 200  # Bybit standard batch size
    
    while current_since < end_ms:
        df = await adapter.fetch_funding_rate_history(symbol, since=current_since, limit=limit)
        if df.empty:
            break
            
        df_filtered = df[df["timestamp"] <= end_ms]
        if df_filtered.empty:
            if df["timestamp"].min() > end_ms:
                break
        else:
            all_dfs.append(df_filtered)
            
        last_ts = int(df["timestamp"].max())
        if last_ts <= current_since:
            break
            
        current_since = last_ts + 1
        await asyncio.sleep(0.2)
        
    if not all_dfs:
        empty = pd.DataFrame(columns=["timestamp", "funding_rate"])
        return empty.astype({"timestamp": "int64", "funding_rate": "float64"})
        
    return pd.concat(all_dfs).drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

@pytest.mark.live
def test_bybit_multi_symbol_funding_and_ohlcv_4months():
    """Verify that we can fetch and validate 4 months of 4h OHLCV and historical funding rates for BTC, ETH, and XRP."""
    print(
        "\nTEST: Live integration test checking 4 months of 4h data and historical "
        "funding rates for BTC, ETH, and XRP from Bybit."
    )

    async def _run():
        exchange_config = _exchange_config()
        
        # Calculate Aligned 4-hour boundaries for a 4-month window
        now_ms = int(time.time() * 1000)
        bar_ms = 4 * 60 * 60 * 1000
        aligned_end_ms = (now_ms // bar_ms - 1) * bar_ms
        aligned_start_ms = aligned_end_ms - (120 * 6 * bar_ms) # Approx 120 days (720 candles)
        
        print(f"\n  Aligned Start: {datetime.fromtimestamp(aligned_start_ms/1000, tz=timezone.utc)}")
        print(f"  Aligned End:   {datetime.fromtimestamp(aligned_end_ms/1000, tz=timezone.utc)}")

        symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT", "XRP/USDT:USDT"]
        
        async with CcxtMarketDataAdapter("bybit", "", "", exchange_config) as adapter:
            for symbol in symbols:
                print(f"\n  Checking symbol: {symbol}")
                
                # 1. Fetch and crop OHLCV
                df_ohlcv = await adapter.fetch_ohlcv(symbol, "4h", limit=1000, since=aligned_start_ms)
                df_ohlcv = df_ohlcv[(df_ohlcv["timestamp"] >= aligned_start_ms) & (df_ohlcv["timestamp"] <= aligned_end_ms)].reset_index(drop=True)
                
                # Enforce complete retrieval
                assert len(df_ohlcv) == 721, f"Expected 721 candles for {symbol}, got {len(df_ohlcv)}"
                
                # 2. Validate metadata
                ohlcv_meta = OHLCVMetadata.from_frame(
                    symbol=symbol,
                    exchange="bybit",
                    timeframe="4h",
                    source="bybit",
                    frame=df_ohlcv,
                    coverage_start_ms=aligned_start_ms,
                    coverage_end_ms=aligned_end_ms,
                    market_type=exchange_config.market_contract.default_type,
                    market_sub_type=exchange_config.market_contract.default_sub_type,
                    settle=exchange_config.market_contract.default_settle,
                )
                assert ohlcv_meta.coverage_status == "COMPLETE"
                assert ohlcv_meta.quality_status == "VALIDATED"
                assert ohlcv_meta.gap_count == 0
                
                print(f"    -> OHLCV Quality: {ohlcv_meta.quality_status} (expected={ohlcv_meta.expected_candles}, total={ohlcv_meta.total_candles})")

                # 3. Fetch and check funding rates
                df_funding = await _fetch_paginated_funding_rate_history(adapter, symbol, aligned_start_ms, aligned_end_ms)
                
                # 4 months is ~120 days * 3 payments/day = ~360 payments
                assert len(df_funding) >= 350, f"Expected ~360 funding rates for {symbol}, got {len(df_funding)}"
                
                print(f"    -> Funding Entries: {len(df_funding)}")
                print(f"    -> First Funding: {df_funding['funding_rate'].iloc[0]} at {datetime.fromtimestamp(df_funding['timestamp'].iloc[0]/1000, tz=timezone.utc)}")
                print(f"    -> Last Funding:  {df_funding['funding_rate'].iloc[-1]} at {datetime.fromtimestamp(df_funding['timestamp'].iloc[-1]/1000, tz=timezone.utc)}")
                
                await asyncio.sleep(0.5) # Anti rate-limit sleep

    asyncio.run(_run())
