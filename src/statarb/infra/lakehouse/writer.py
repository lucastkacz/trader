from pathlib import Path
from typing import Union

import duckdb
import pandas as pd
from statarb.infra.observability.logger import setup_logger

logger = setup_logger(__name__)

class ParquetWriter:
    """
    Handles writing market data to Hive-partitioned Parquet files.
    Structure: {lake_dir}/exchange={exchange}/timeframe={timeframe}/symbol={symbol}/data.parquet
    """

    def __init__(self, lake_dir: Union[str, Path]):
        self.lake_dir = Path(lake_dir)
        self.lake_dir.mkdir(parents=True, exist_ok=True)
        # In-memory connection for orchestration
        self.conn = duckdb.connect()

    def _get_partition_path(self, exchange: str, timeframe: str, symbol: str) -> Path:
        # Sanitize symbol (BTC/USDT -> BTC-USDT)
        safe_symbol = symbol.replace("/", "-")
        return self.lake_dir / f"exchange={exchange}" / f"timeframe={timeframe}" / f"symbol={safe_symbol}"

    def write(self, df: pd.DataFrame, symbol: str, exchange: str, timeframe: str):
        """
        Upserts OHLCV data to the lakehouse.
        """
        if df.empty:
            return

        # Ensure schema
        required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            logger.error(f"DataFrame missing required columns: {required_cols}")
            return

        # Normalize Timestamp
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        if df['timestamp'].dt.tz is not None:
             df['timestamp'] = df['timestamp'].dt.tz_convert('UTC').dt.tz_localize(None)

        partition_dir = self._get_partition_path(exchange, timeframe, symbol)
        partition_dir.mkdir(parents=True, exist_ok=True)
        file_path = partition_dir / "data.parquet"

        # Prepare for DuckDB
        df_new = df[required_cols].copy()
        self.conn.register('new_data', df_new)

        try:
            if file_path.exists():
                # Deduplication Merge
                cols_str = ', '.join(required_cols)
                query = f"""
                    COPY (
                        WITH combined AS (
                            SELECT {cols_str}, 1 as priority FROM new_data
                            UNION ALL
                            SELECT {cols_str}, 2 as priority FROM '{str(file_path)}'
                        ),
                        ranked AS (
                            SELECT *, ROW_NUMBER() OVER (PARTITION BY timestamp ORDER BY priority ASC) as rn
                            FROM combined
                        )
                        SELECT {cols_str} FROM ranked WHERE rn = 1 ORDER BY timestamp ASC
                    ) TO '{str(file_path)}' (FORMAT PARQUET);
                """
                self.conn.execute(query)
            else:
                # Direct Write
                self.conn.execute(f"COPY (SELECT * FROM new_data ORDER BY timestamp ASC) TO '{str(file_path)}' (FORMAT PARQUET)")
            
            logger.debug(f"Wrote {len(df)} rows to {file_path}")

        except Exception as e:
            logger.error(f"Failed to write data for {symbol}: {e}")
            raise e
        finally:
            self.conn.unregister('new_data')
