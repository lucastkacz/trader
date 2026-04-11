import os
import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd
from typing import Dict, Any

class ParquetStorage:
    """
    High-Performance Object Storage utilizing Apache Parquet.
    Specifically architects Custom Metadata Injection into the binary headers.
    """
    def __init__(self, base_dir: str = "data/parquet"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        
    def _get_path(self, symbol: str, timeframe: str) -> str:
        # E.g. data/parquet/4h/BTC_USDT.parquet
        tf_dir = os.path.join(self.base_dir, timeframe)
        os.makedirs(tf_dir, exist_ok=True)
        clean_symbol = symbol.replace("/", "_").replace(":", "_")
        return os.path.join(tf_dir, f"{clean_symbol}.parquet")

    def save_ohlcv(self, symbol: str, timeframe: str, df: pd.DataFrame, custom_metadata: Dict[str, str]):
        """
        Takes a Pandas DataFrame, converts it to an Arrow Table,
        injects string-value metadata dictionaries directly into the internal schema,
        and serializes to disk. 
        """
        filepath = self._get_path(symbol, timeframe)
        
        # 1. Convert to native Arrow Table
        table = pa.Table.from_pandas(df)
        
        # 2. Reconstruct Metadata
        # Arrow physically mandates metadata to be binary (bytes). 
        # Python dicts are strings. We must encode them.
        existing_metadata = table.schema.metadata if table.schema.metadata else {}
        
        # Inject our Custom Payload
        encoded_payload = {key.encode(): val.encode() for key, val in custom_metadata.items()}
        merged_metadata = {**existing_metadata, **encoded_payload}
        
        # 3. Mount modified schema
        new_schema = table.schema.with_metadata(merged_metadata)
        new_table = table.cast(new_schema)
        
        # 4. Flush to disk (using aggressive Snappy compression by default)
        pq.write_table(new_table, filepath)

    def read_metadata(self, symbol: str, timeframe: str) -> Dict[str, str]:
        """
        Reads STRICTLY the binary header of a Parquet file natively using PyArrow.
        Does NOT load the internal Dataframe Payload. Zero risk of RAM OOM.
        """
        filepath = self._get_path(symbol, timeframe)
        if not os.path.exists(filepath):
            return {}
            
        # Natively reads just the Schema Footer
        parquet_file = pq.ParquetFile(filepath)
        raw_metadata = parquet_file.schema_arrow.metadata
        
        if not raw_metadata:
            return {}
            
        # Decode binary back to string dictionary map
        decoded_map = {}
        for key, val in raw_metadata.items():
            # Skip native Pandas schema binary payloads
            if key == b"pandas":
                continue
            decoded_map[key.decode('utf-8')] = val.decode('utf-8')
            
        return decoded_map

    def load_ohlcv(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """
        Standard operational read method. Loads the file fully into a Pandas Context.
        """
        filepath = self._get_path(symbol, timeframe)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Parquet cache missing for {symbol} @ {timeframe}")
            
        return pq.read_table(filepath).to_pandas()
