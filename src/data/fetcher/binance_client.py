import ccxt.async_support as ccxt
import pandas as pd
from typing import List, Dict, Any

from src.core.logger import logger, LogContext
from src.core.config import settings

def _get_exchange() -> ccxt.binance:
    """Internal factory to yield a rate-limited async exchange instance."""
    return ccxt.binance({
        "enableRateLimit": True,
        "options": {"defaultType": "future"}, # USD-M Perpetuals
        "apiKey": settings.binance_api_key,
        "secret": settings.binance_api_secret,
    })

async def fetch_usd_m_universe(min_volume: float = 20_000_000) -> List[str]:
    """
    Fetches all active Binance futures and filters out dead/illiquid pairs.
    Strips the CCXT internal ":USDT" suffix to maintain standardized pairs.
    """
    exchange = _get_exchange()
    try:
        # We explicitly load all tickers for volume cross-checking
        tickers = await exchange.fetch_tickers()
        valid_pairs = []
        
        for symbol, data in tickers.items():
            quote_volume = float(data.get("quoteVolume", 0))
            if quote_volume > min_volume:
                # CCXT parses USD-M futures with a colon like "BTC/USDT:USDT"
                # For engine compatibility, we enforce "BTC/USDT"
                clean_symbol = symbol.split(":")[0]
                valid_pairs.append(clean_symbol)
                
        ctx = LogContext(trade_id="UNIVERSE_SCAN")
        logger.bind(**ctx.model_dump(exclude_none=True)).info(
            f"Filtered Universe: {len(valid_pairs)} assets found above ${min_volume} volume."
        )
        return valid_pairs
    except Exception as e:
        logger.error(f"Failed pulling universe: {str(e)}")
        raise RuntimeError(f"Universe Error: {str(e)}")
    finally:
        await exchange.close()

async def fetch_klines(symbol: str, timeframe: str = "4h", limit: int = 1000) -> pd.DataFrame:
    """
    Downloads bulk historical OHLCV data.
    If Binance returns a 502/Timeout, it intercepts the ccxt.NetworkError
    so the upstream engine can enact its Blackout Amnesty Protocol.
    """
    exchange = _get_exchange()
    # Engine uses standard CCXT nomenclature but requires the ":" suffix to query USD-M explicit
    ccxt_symbol = f"{symbol}:USDT" if ":" not in symbol else symbol
    
    ctx = LogContext(pair=symbol)
    logger.bind(**ctx.model_dump(exclude_none=True)).debug(f"Fetching {limit} candles for {timeframe}")
    
    try:
        ohlcv = await exchange.fetch_ohlcv(ccxt_symbol, timeframe, limit=limit)
        
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        # Cast to strict floats as per architectural manifesto
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
            
        return df
        
    except ccxt.NetworkError as ne:
        logger.bind(**ctx.model_dump(exclude_none=True)).error(f"Network Timeout/502: {str(ne)}")
        # Raise generic RuntimeError for Red-Team auditor mock handling
        raise RuntimeError(f"NetworkError: {str(ne)}")
    except Exception as base_e:
        logger.bind(**ctx.model_dump(exclude_none=True)).critical(f"FATAL ccxt execution: {str(base_e)}")
        raise
    finally:
        await exchange.close()
