import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict

def get_file_path(data_dir: Path, exchange_id: str, timeframe: str, symbol: str) -> Path:
    """Standardizes file path generation."""
    safe_symbol = symbol.replace('/', '_')
    return data_dir / exchange_id / timeframe / f"{safe_symbol}.parquet"

def get_stored_metadata(file_path: Path) -> Dict:
    """
    Reads Parquet metadata without loading the file to check coverage.
    Returns a dict with 'start_date', 'end_date', 'rows', etc.
    """
    if not file_path.exists():
        return {}
        
    try:
        # Read file metadata only
        parquet_file = pq.ParquetFile(file_path)
        metadata = parquet_file.metadata
        kv_metadata = metadata.metadata or {}
        
        # Decode bytes keys/values
        decoded = {}
        for k, v in kv_metadata.items():
            if v is not None:
                decoded[k.decode('utf-8')] = v.decode('utf-8')
                
        # If we have our custom bounds, use them
        if 'start_date' in decoded and 'end_date' in decoded:
            return {
                'start_date': datetime.strptime(decoded['start_date'], '%Y-%m-%d %H:%M:%S'),
                'end_date': datetime.strptime(decoded['end_date'], '%Y-%m-%d %H:%M:%S'),
                'rows': int(decoded.get('rows', 0))
            }
            
        # Fallback: Read columns if metadata missing (slower but necessary if custom meta absent)
        # Note: avoiding full read if possible. 
        # Actually, for correctness if custom meta is missing, might need to read index.
        # But let's assume we rely on our custom metadata for speed, or return empty if unsafe.
        return {}
        
    except Exception as e:
        print(f"Error reading metadata from {file_path}: {e}")
        return {}

def load_data(file_path: Path, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> pd.DataFrame:
    """
    Loads data from Parquet, optionally filtering by date range.
    """
    if not file_path.exists():
        return pd.DataFrame()
        
    try:
        # We can push down predicates to parquet read for speed
        filters = []
        if start_date:
            filters.append(('timestamp', '>=', start_date))
        if end_date:
            filters.append(('timestamp', '<=', end_date))
            
        # Pushing down filters with pandas read_parquet is supported via pyarrow
        # But generic read then filter is safer for complex timestamp types if pyarrow version varies.
        # Let's read then filter for robustness unless file is huge.
        df = pd.read_parquet(file_path)
        
        # Filter
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
            
        return df
    except Exception as e:
        print(f"Error loading data {file_path}: {e}")
        return pd.DataFrame()

def save_data(new_df: pd.DataFrame, file_path: Path, exchange: str, symbol: str):
    """
    Merges new data with existing file, deduplicates, sorts, and saves with updated metadata.
    """
    if new_df.empty:
        return

    # Ensure parent dir exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    final_df = new_df
    
    # Merge if exists
    if file_path.exists():
        try:
            stored_df = pd.read_parquet(file_path)
            # Combine
            final_df = pd.concat([stored_df, new_df])
            # Deduplicate by index (timestamp)
            final_df = final_df[~final_df.index.duplicated(keep='last')]
            final_df = final_df.sort_index()
        except Exception as e:
            print(f"Error merging with existing file {file_path}: {e}. Overwriting.")
            final_df = new_df

    # Calculate Metadata
    if final_df.empty:
        return

    meta_start = final_df.index.min().strftime('%Y-%m-%d %H:%M:%S')
    meta_end = final_df.index.max().strftime('%Y-%m-%d %H:%M:%S')
    
    # Convert to Table
    table = pa.Table.from_pandas(final_df)
    
    # Add Custom Metadata
    existing_meta = table.schema.metadata or {}
    custom_meta = {
        'start_date': meta_start,
        'end_date': meta_end,
        'rows': str(len(final_df)),
        'symbol': symbol,
        'exchange': exchange,
        'updated_at': datetime.now().isoformat()
    }
    
    for k, v in custom_meta.items():
        existing_meta[k.encode('utf-8')] = v.encode('utf-8')
        
    table = table.replace_schema_metadata(existing_meta)
    
    # Write
    pq.write_table(table, file_path, write_statistics=True)
