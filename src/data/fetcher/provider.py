import ccxt
import time
import pandas as pd
from datetime import datetime
from typing import Optional, List, Callable, Dict, Any

def get_exchange(exchange_id: str) -> ccxt.Exchange:
    """Initializes and returns the CCXT exchange instance."""
    try:
        exchange_class = getattr(ccxt, exchange_id)
        return exchange_class()
    except getattr:
        raise ValueError(f"Exchange '{exchange_id}' not found in CCXT.")

def fetch_ohlcv_range(
    exchange: ccxt.Exchange, 
    symbol: str, 
    timeframe: str, 
    start_date: datetime, 
    end_date: datetime,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> List[List[float]]:
    """
    Fetches OHLCV data for a specific range, handling pagination and rate limits.
    Returns list of raw OHLCV lists (timestamp, open, high, low, close, volume).
    """
    all_ohlcv = []
    
    # Timestamps in ms
    since = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)
    limit = 1000
    
    current_since = since
    
    total_duration = end_ts - since
    if total_duration <= 0:
        return []

    print(f"  Fetching segment: {start_date} -> {end_date}")

    while True:
        try:
            # Rate Limit
            if exchange.rateLimit:
                time.sleep(exchange.rateLimit / 1000)
            
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=current_since, limit=limit)
            
            if not ohlcv:
                break
                
            last_ts = ohlcv[-1][0]
            all_ohlcv.extend(ohlcv)
            current_since = last_ts + 1
            
            # Progress update (local to this segment)
            if progress_callback:
                current_duration = last_ts - since
                # We normalize this later in the main loop, but here is fine too
                # For now, let's just log or let parent handle overall progress
                pass

            if last_ts >= end_ts:
                break
                
        except Exception as e:
            print(f"Error checking exchange: {e}")
            raise e
            
    return all_ohlcv

def fetch_funding_rate_history(
    exchange: ccxt.Exchange, 
    symbol: str, 
    start_date: datetime, 
    end_date: datetime
) -> List[Dict]:
    """
    Fetches funding rate history if supported.
    """
    if not exchange.has.get('fetchFundingRateHistory'):
        return []

    all_funding = []
    since = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)
    limit = 1000
    
    current_since = since
    
    # Simple pagination loop similar to OHLCV
    while True:
        try:
            if exchange.rateLimit:
                time.sleep(exchange.rateLimit / 1000)
                
            rates = exchange.fetch_funding_rate_history(symbol, since=current_since, limit=limit)
            
            if not rates:
                break
                
            last_ts = rates[-1]['timestamp']
            all_funding.extend(rates)
            current_since = last_ts + 1
            
            if last_ts >= end_ts:
                break
                
        except Exception as e:
            # Depending on exchange, this might fail gracefully or not
            print(f"Error fetching funding rates: {e}")
            break
            
    return all_funding

def get_market_tickers(exchange_id: str, limit: int = 50) -> pd.DataFrame:
    """
    Fetches top tickers by quote volume.
    """
    try:
        exchange = get_exchange(exchange_id)
        exchange.load_markets()
        tickers = exchange.fetch_tickers()
        
        data = []
        for symbol, ticker in tickers.items():
            # Basic screen for USDT pairs (customizable later)
            if '/USDT' not in symbol:
                continue
                
            quote_vol = ticker.get('quoteVolume')
            if quote_vol is None:
                continue
                
            data.append({
                'Symbol': symbol,
                'Price': ticker.get('last'),
                '24h Vol (M)': quote_vol / 1_000_000,
                '24h Change %': ticker.get('percentage'),
            })
            
        df = pd.DataFrame(data)
        if df.empty:
            return df
            
        df = df.sort_values('24h Vol (M)', ascending=False).head(limit)
        return df.reset_index(drop=True)
        
    except Exception as e:
        print(f"Error fetching markets: {e}")
        return pd.DataFrame()

def get_all_symbols(exchange_id: str) -> List[str]:
    try:
        exchange = get_exchange(exchange_id)
        exchange.load_markets()
        return sorted(exchange.symbols)
    except Exception as e:
        print(f"Error fetching symbols: {e}")
        return []
