import duckdb
import pandas as pd
from pathlib import Path
from typing import Optional, Union, List
from lib.utils.logger import setup_logger

logger = setup_logger(__name__)

class MarketDataDB:
    """
    Manages the storage and retrieval of OHLCV market data using DuckDB and Partitioned Parquet files.
    
    Architecture (Hive Partitioning):
        Data is stored in a directory structure, not a single monolithic file.
        Structure:
            {data_dir}/
                exchange={exchange}/
                    timeframe={timeframe}/
                        symbol={symbol}/
                            data.parquet
                            
    Benefits:
        1. Maintainability: Easy to delete or fix specific symbols (just delete the folder).
        2. Performance: DuckDB's 'hive_partitioning' allows it to prune huge amounts of data
           by just looking at folder names. It only reads the files it needs.
        3. Space: 'exchange', 'timeframe', and 'symbol' are implied by the folder structure
           and are NOT stored inside the Parquet files, saving disk space.
    """
    
    def __init__(self, data_dir: Union[str, Path] = "market_data"):
        """
        Initializes the database manager.
        
        Args:
            data_dir: The root directory where data will be stored.
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # We use an in-memory DuckDB connection to orchestrate the Parquet reads/writes.
        self.conn = duckdb.connect() 

    def _get_partition_path(self, exchange: str, timeframe: str, symbol: str) -> Path:
        """Helper to construct the path for a specific partition."""
        # Sanitize symbol for filesystem (e.g., BTC/USDT -> BTC-USDT)
        safe_symbol = symbol.replace("/", "-")
        return self.data_dir / f"exchange={exchange}" / f"timeframe={timeframe}" / f"symbol={safe_symbol}"

    def save_ohlcv(self, df: pd.DataFrame, symbol: str, exchange: str, timeframe: str):
        """
        Saves OHLCV data to a partitioned Parquet file.
        Performs an Upsert (Merge) if data already exists to prevent duplicates.
        """
        if df.empty:
            return

        # 1. Prepare new data
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
             df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Ensure UTC-Naive for consistency
        if df['timestamp'].dt.tz is not None:
            df['timestamp'] = df['timestamp'].dt.tz_convert('UTC').dt.tz_localize(None)

        # Only keep the metric columns. 
        # Metadata (symbol, exchange, timeframe) is stored in the folder structure.
        store_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        
        # Verify columns exist
        missing = [c for c in store_cols if c not in df.columns]
        if missing:
            logger.error(f"Dataframe missing columns: {missing}")
            return

        df_new = df[store_cols].copy()

        # 2. Determine File Path
        partition_dir = self._get_partition_path(exchange, timeframe, symbol)
        partition_dir.mkdir(parents=True, exist_ok=True)
        file_path = partition_dir / "data.parquet"

        try:
            # 3. Merge with existing data if needed
            if file_path.exists():
                # Register new data as a virtual table
                self.conn.register('new_data', df_new)
                
                # Perform a Deduplication Merge using DuckDB
                # We prioritize the 'new_data' if there's a timestamp collision
                # Explicitly listing columns to avoid schema mismatch
                cols_str = ', '.join(store_cols)
                dedup_query = f"""
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
                        SELECT {cols_str} 
                        FROM ranked 
                        WHERE rn = 1
                        ORDER BY timestamp ASC
                    ) TO '{str(file_path)}' (FORMAT PARQUET);
                """
                self.conn.execute(dedup_query)
                self.conn.unregister('new_data')
            else:
                # Just write the new file
                self.conn.register('new_data', df_new)
                self.conn.execute(f"COPY (SELECT * FROM new_data ORDER BY timestamp ASC) TO '{str(file_path)}' (FORMAT PARQUET)")
                self.conn.unregister('new_data')
                
            logger.info(f"Saved {len(df)} rows for {symbol} to {file_path}")

        except Exception as e:
            logger.error(f"Error saving data for {symbol}: {e}")
            raise e

    def load_ohlcv(self, symbol: str, exchange: str, timeframe: str, 
                   start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Loads OHLCV data from the specific Parquet partition.
        """
        partition_path = self._get_partition_path(exchange, timeframe, symbol)
        file_path = partition_path / "data.parquet"
        
        if not file_path.exists():
            return pd.DataFrame()
            
        # We query the specific file directly for speed
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
            
            # Re-attach metadata columns expected by consumers
            df['symbol'] = symbol
            df['exchange'] = exchange
            df['timeframe'] = timeframe
            return df
        except Exception as e:
            logger.error(f"Error loading data for {symbol}: {e}")
            return pd.DataFrame()
    
    def count_rows(self, symbol: str, exchange: str, timeframe: str, start_ts: int, end_ts: int) -> int:
        """
        Counts the number of rows available in the given range.
        Args:
            start_ts: Timestamp in milliseconds.
            end_ts: Timestamp in milliseconds.
        """
        partition_path = self._get_partition_path(exchange, timeframe, symbol)
        file_path = partition_path / "data.parquet"
        
        if not file_path.exists():
            return 0
            
        try:
            # Convert ms timestamps back to datetime for query
            start_dt = pd.to_datetime(start_ts, unit='ms', utc=True).tz_localize(None)
            end_dt = pd.to_datetime(end_ts, unit='ms', utc=True).tz_localize(None)
            
            query = f"SELECT count(*) FROM '{str(file_path)}' WHERE timestamp >= ? AND timestamp <= ?"
            result = self.conn.execute(query, [start_dt, end_dt]).fetchone()
            
            return result[0] if result else 0
        except Exception:
            return 0

    def get_available_symbols(self, exchange: Optional[str] = None, timeframe: Optional[str] = None) -> List[str]:
        """
        Returns a list of unique symbols in the database by scanning the directory structure.
        """
        try:
            # We use DuckDB's hive partitioning reader to scan the folders
            # Pattern: data_dir / exchange=... / timeframe=... / symbol=... / data.parquet
            query = f"SELECT DISTINCT symbol FROM read_parquet('{self.data_dir}/*/*/*/*.parquet', hive_partitioning=1) WHERE 1=1"
            params = []
            
            if exchange:
                query += " AND exchange = ?"
                params.append(exchange)
            
            if timeframe:
                query += " AND timeframe = ?"
                params.append(timeframe)
                
            result = self.conn.execute(query, params).fetchall()
            
            # The symbols returned are the directory names (e.g., 'BTC-USDT')
            # We convert them back to 'BTC/USDT' for standard usage
            return [row[0].replace('-', '/') for row in result]
            
        except Exception:
            # If directory is empty or path doesn't exist
            return []

    def get_first_timestamp(self, symbol: str, exchange: str, timeframe: str) -> Optional[pd.Timestamp]:
        """
        Retrieves the earliest timestamp available for a given symbol.
        """
        partition_path = self._get_partition_path(exchange, timeframe, symbol)
        file_path = partition_path / "data.parquet"
        
        if not file_path.exists():
            return None
        
        try:
            query = f"SELECT MIN(timestamp) FROM '{str(file_path)}'"
            result = self.conn.execute(query).fetchone()
            
            if result and result[0]:
                return pd.to_datetime(result[0])
        except Exception:
            pass
            
        return None

    def get_last_timestamp(self, symbol: str, exchange: str, timeframe: str) -> Optional[pd.Timestamp]:
        """
        Retrieves the latest timestamp available for a given symbol.
        """
        partition_path = self._get_partition_path(exchange, timeframe, symbol)
        file_path = partition_path / "data.parquet"
        
        if not file_path.exists():
            return None
        
        try:
            query = f"SELECT MAX(timestamp) FROM '{str(file_path)}'"
            result = self.conn.execute(query).fetchone()
            
            if result and result[0]:
                return pd.to_datetime(result[0])
        except Exception:
            pass
            
        return None

    def get_close_prices_pivot(
        self, 
        exchange: str, 
        timeframe: str, 
        symbols: List[str], 
        start_date: str, 
        end_date: str
    ) -> pd.DataFrame:
        """
        Retrieves close prices for multiple symbols aligned by timestamp.
        Returns a DataFrame where Index=Timestamp, Columns=Symbols.
        Handles missing data by inserting NULLs (Outer Join behavior via Pivot).
        """
        # 1. Identify valid files and map symbols
        valid_paths = []
        valid_symbols = []
        
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        for sym in symbols:
            partition_path = self._get_partition_path(exchange, timeframe, sym)
            file_path = partition_path / "data.parquet"
            if file_path.exists():
                valid_paths.append(str(file_path))
                valid_symbols.append(sym)
            else:
                logger.warning(f"Excluding {sym}: No data found in storage.")

        if not valid_paths:
            return pd.DataFrame()

        # 2. Construct Query
        # We read from the list of specific files.
        # We need to manually inject the 'symbol' column because it's not in the parquet file
        # (it was in the folder structure). 
        # Since we can't easily use read_parquet with a list AND hive partitioning inference simultaneously 
        # for a specific subset in a complex way, we'll use a UNION ALL approach for the selected files.
        
        # However, for speed with many files, creating a temporary view or using read_parquet with a list is better.
        # DuckDB's read_parquet accepts a list of files. But we lose the 'symbol' info if it's not in the file.
        # The file DOES NOT have the symbol column.
        
        # robust approach: specific selects with union
        sub_queries = []
        for sym, path in zip(valid_symbols, valid_paths):
            sub_queries.append(f"SELECT timestamp, close, '{sym}' as symbol FROM '{path}' WHERE timestamp >= '{start_dt}' AND timestamp <= '{end_dt}'")
        
        full_union_query = " UNION ALL ".join(sub_queries)
        
        pivot_query = f"""
            PIVOT (
                {full_union_query}
            ) ON symbol USING first(close) ORDER BY timestamp ASC
        """
        
        try:
            df = self.conn.execute(pivot_query).df()
            if not df.empty:
                df = df.set_index('timestamp')
            return df
        except Exception as e:
            logger.error(f"Error executing pivot query: {e}")
            return pd.DataFrame()

    def close(self):
        """Closes the DuckDB connection."""
        self.conn.close()
