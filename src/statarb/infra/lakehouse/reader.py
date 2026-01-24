from pathlib import Path
from typing import Optional, Union, List

import duckdb
import pandas as pd
from statarb.infra.observability.logger import setup_logger

logger = setup_logger(__name__)

class DuckDBReader:
    """
    Reads market data from the Hive-partitioned Parquet Store.
    """

    def __init__(self, lake_dir: Union[str, Path]):
        self.lake_dir = Path(lake_dir)
        self.conn = duckdb.connect()

    def _get_partition_path(self, exchange: str, timeframe: str, symbol: str) -> Path:
        safe_symbol = symbol.replace("/", "-")
        return self.lake_dir / f"exchange={exchange}" / f"timeframe={timeframe}" / f"symbol={safe_symbol}"

    def load_ohlcv(self, symbol: str, exchange: str, timeframe: str, 
                   start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        
        partition_path = self._get_partition_path(exchange, timeframe, symbol)
        file_path = partition_path / "data.parquet"

        if not file_path.exists():
            return pd.DataFrame()

        query = f"SELECT * FROM '{str(file_path)}' WHERE 1=1"
        params = []

        if start_date:
            query += " AND timestamp >= ?"
            params.append(pd.to_datetime(start_date))
        if end_date:
            query += " AND timestamp <= ?"
            params.append(pd.to_datetime(end_date))
        
        query += " ORDER BY timestamp ASC"

        try:
            df = self.conn.execute(query, params).df()
            # Attach metadata
            df['symbol'] = symbol
            df['exchange'] = exchange
            df['timeframe'] = timeframe
            return df
        except Exception as e:
            logger.error(f"Error reading {symbol}: {e}")
            return pd.DataFrame()

    def get_last_timestamp(self, symbol: str, exchange: str, timeframe: str) -> Optional[pd.Timestamp]:
        path = self._get_partition_path(exchange, timeframe, symbol) / "data.parquet"
        if not path.exists():
            return None
        try:
            res = self.conn.execute(f"SELECT MAX(timestamp) FROM '{str(path)}'").fetchone()
            if res and res[0]:
                return pd.to_datetime(res[0])
        except Exception:
            pass
        return None
    
    def get_first_timestamp(self, symbol: str, exchange: str, timeframe: str) -> Optional[pd.Timestamp]:
        path = self._get_partition_path(exchange, timeframe, symbol) / "data.parquet"
        if not path.exists():
            return None
        try:
            res = self.conn.execute(f"SELECT MIN(timestamp) FROM '{str(path)}'").fetchone()
            if res and res[0]:
                return pd.to_datetime(res[0])
        except Exception:
            pass
        return None

    def count_rows(self, symbol: str, exchange: str, timeframe: str, start_ts: int, end_ts: int) -> int:
        path = self._get_partition_path(exchange, timeframe, symbol) / "data.parquet"
        if not path.exists():
            return 0
        
        start_dt = pd.to_datetime(start_ts, unit='ms', utc=True).tz_localize(None)
        end_dt = pd.to_datetime(end_ts, unit='ms', utc=True).tz_localize(None)

        try:
            res = self.conn.execute(f"SELECT count(*) FROM '{str(path)}' WHERE timestamp >= ? AND timestamp <= ?", [start_dt, end_dt]).fetchone()
            return res[0] if res else 0
        except Exception:
            return 0
