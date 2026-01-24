from typing import Optional, Union, List
from pathlib import Path
import pandas as pd

from .writer import ParquetWriter
from .reader import DuckDBReader

class MarketDataStore:
    """
    Unified facade for Market Data storage (Writer) and retrieval (Reader).
    Replaces the old MarketDataDB.
    """
    def __init__(self, lake_dir: Union[str, Path]):
        self.writer = ParquetWriter(lake_dir)
        self.reader = DuckDBReader(lake_dir)

    def save_ohlcv(self, df: pd.DataFrame, symbol: str, exchange: str, timeframe: str):
        self.writer.write(df, symbol, exchange, timeframe)

    def load_ohlcv(self, symbol: str, exchange: str, timeframe: str, start_date=None, end_date=None) -> pd.DataFrame:
        return self.reader.load_ohlcv(symbol, exchange, timeframe, start_date, end_date)

    def get_last_timestamp(self, symbol: str, exchange: str, timeframe: str):
        return self.reader.get_last_timestamp(symbol, exchange, timeframe)

    def get_first_timestamp(self, symbol: str, exchange: str, timeframe: str):
        return self.reader.get_first_timestamp(symbol, exchange, timeframe)

    def count_rows(self, symbol: str, exchange: str, timeframe: str, start_ts: int, end_ts: int) -> int:
        return self.reader.count_rows(symbol, exchange, timeframe, start_ts, end_ts)
    
    def close(self):
        self.writer.conn.close()
        self.reader.conn.close()

# Alias for backward compatibility if needed, though we should prefer MarketDataStore
MarketDataDB = MarketDataStore
