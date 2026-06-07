from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict

class FundingMetadata(BaseModel):
    """Typed metadata persisted with a stored funding dataset."""
    model_config = ConfigDict(extra="ignore")

    schema_version: int = 1
    symbol: str
    exchange: str
    updated_at: str

    @classmethod
    def create(cls, symbol: str, exchange: str) -> FundingMetadata:
        return cls(
            symbol=symbol,
            exchange=exchange,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

class LocalFundingStore:
    """Local Parquet-backed store for historical funding rate datasets."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.root = Path(base_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for_funding(
        self,
        symbol: str,
        exchange: str,
        *,
        create_parent: bool = False,
    ) -> Path:
        """Return the local Parquet path for one symbol/exchange funding history."""
        funding_dir = self.root / exchange.lower() / "funding"
        if create_parent:
            funding_dir.mkdir(parents=True, exist_ok=True)
        clean_symbol = self._clean_symbol(symbol)
        return funding_dir / f"{clean_symbol}.parquet"

    def save_funding(
        self,
        symbol: str,
        exchange: str,
        df: pd.DataFrame,
    ) -> None:
        """Save historical funding rates to a local Parquet dataset."""
        filepath = self.path_for_funding(symbol, exchange, create_parent=True)
        
        # Ensure correct column types and sorting
        if not df.empty:
            df = df.loc[:, ["timestamp", "funding_rate"]].copy()
            df["timestamp"] = df["timestamp"].astype("int64")
            df["funding_rate"] = df["funding_rate"].astype("float64")
            df = df.drop_duplicates(subset=["timestamp"], keep="last")
            df = df.sort_values("timestamp").reset_index(drop=True)
        else:
            df = pd.DataFrame(columns=["timestamp", "funding_rate"])
            df = df.astype({"timestamp": "int64", "funding_rate": "float64"})

        metadata = FundingMetadata.create(symbol=symbol, exchange=exchange)
        table = pa.Table.from_pandas(df, preserve_index=False)
        encoded_metadata = {
            key.encode("utf-8"): str(value).encode("utf-8")
            for key, value in metadata.model_dump().items()
        }
        new_schema = table.schema.with_metadata(encoded_metadata)
        pq.write_table(table.cast(new_schema), filepath)

    def load_funding(self, symbol: str, exchange: str) -> pd.DataFrame:
        """Load local funding rate dataset, returning empty DataFrame if missing."""
        filepath = self.path_for_funding(symbol, exchange)
        if not filepath.exists():
            df = pd.DataFrame(columns=["timestamp", "funding_rate"])
            return df.astype({"timestamp": "int64", "funding_rate": "float64"})

        df = pq.read_table(filepath).to_pandas()
        if not df.empty:
            df = df.loc[:, ["timestamp", "funding_rate"]].copy()
            df["timestamp"] = df["timestamp"].astype("int64")
            df["funding_rate"] = df["funding_rate"].astype("float64")
            df = df.sort_values("timestamp").reset_index(drop=True)
        return df

    def read_metadata(self, symbol: str, exchange: str) -> dict[str, str]:
        """Read only the Parquet schema metadata for one funding dataset."""
        filepath = self.path_for_funding(symbol, exchange)
        if not filepath.exists():
            return {}

        parquet_file = pq.ParquetFile(filepath)
        raw_metadata = parquet_file.schema_arrow.metadata
        if not raw_metadata:
            return {}

        decoded_map = {}
        for key, val in raw_metadata.items():
            if key == b"pandas":
                continue
            decoded_map[key.decode("utf-8")] = val.decode("utf-8")
        return decoded_map

    @staticmethod
    def _clean_symbol(symbol: str) -> str:
        return symbol.replace("/", "_").replace(":", "_")
