import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from typing import Mapping

from src.data.ohlcv import OHLCVMetadata, normalize_ohlcv_frame

CANONICAL_METADATA_KEYS = set(OHLCVMetadata.model_fields) | {"status"}


class LocalOHLCVParquetStore:
    """Local Parquet-backed store for canonical OHLCV datasets."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.root = Path(base_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        exchange: str,
        *,
        create_parent: bool = False,
    ) -> Path:
        """Return the local Parquet path for one exchange/timeframe/symbol."""
        timeframe_dir = self.root / exchange.lower() / timeframe
        if create_parent:
            timeframe_dir.mkdir(parents=True, exist_ok=True)
        clean_symbol = self._clean_symbol(symbol)
        return timeframe_dir / f"{clean_symbol}.parquet"

    def save_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        custom_metadata: Mapping[str, object] | OHLCVMetadata,
        exchange: str,
    ) -> None:
        """Normalize and replace one local OHLCV Parquet dataset."""
        filepath = self.path_for_ohlcv(symbol, timeframe, exchange, create_parent=True)
        normalized = normalize_ohlcv_frame(df)
        metadata = self._metadata_for_write(
            symbol=symbol,
            timeframe=timeframe,
            exchange=exchange,
            frame=normalized,
            custom_metadata=custom_metadata,
        )

        table = pa.Table.from_pandas(normalized, preserve_index=False)
        existing_metadata = table.schema.metadata if table.schema.metadata else {}
        encoded_payload = {
            key.encode("utf-8"): value.encode("utf-8")
            for key, value in metadata.items()
        }
        merged_metadata = {**existing_metadata, **encoded_payload}
        new_schema = table.schema.with_metadata(merged_metadata)
        pq.write_table(table.cast(new_schema), filepath)

    def read_metadata(self, symbol: str, timeframe: str, exchange: str) -> dict[str, str]:
        """Read only the Parquet schema metadata for one OHLCV dataset."""
        filepath = self.path_for_ohlcv(symbol, timeframe, exchange)
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

    def read_ohlcv_metadata(
        self,
        symbol: str,
        timeframe: str,
        exchange: str,
    ) -> OHLCVMetadata | None:
        """Read typed OHLCV metadata, returning None when the file is missing."""
        metadata = self.read_metadata(symbol, timeframe, exchange)
        if not metadata:
            return None
        return OHLCVMetadata.from_mapping(
            metadata,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
        )

    def load_ohlcv(self, symbol: str, timeframe: str, exchange: str) -> pd.DataFrame:
        """Load one local OHLCV dataset and normalize its DataFrame contract."""
        filepath = self.path_for_ohlcv(symbol, timeframe, exchange)
        if not filepath.exists():
            raise FileNotFoundError(f"Parquet cache missing for {symbol} @ {timeframe}")

        return normalize_ohlcv_frame(pq.read_table(filepath).to_pandas())

    def _metadata_for_write(
        self,
        *,
        symbol: str,
        timeframe: str,
        exchange: str,
        frame: pd.DataFrame,
        custom_metadata: Mapping[str, object] | OHLCVMetadata,
    ) -> dict[str, str]:
        if isinstance(custom_metadata, OHLCVMetadata):
            return custom_metadata.to_parquet_metadata()

        custom = {str(key): str(value) for key, value in custom_metadata.items()}
        base = OHLCVMetadata.from_frame(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            source=custom.get("source", exchange),
            frame=frame,
            coverage_status=custom.get("coverage_status") or custom.get("status"),
            coverage_start_ms=_int_or_none(custom.get("coverage_start_ms")),
            coverage_end_ms=_int_or_none(custom.get("coverage_end_ms")),
            last_closed_candle_ms=_int_or_none(custom.get("last_closed_candle_ms")),
            market_type=_str_or_none(custom.get("market_type")),
            market_sub_type=_str_or_none(custom.get("market_sub_type")),
            settle=_str_or_none(custom.get("settle")),
        ).to_parquet_metadata()
        custom_payload = {
            key: value
            for key, value in custom.items()
            if key not in CANONICAL_METADATA_KEYS
        }
        return {**base, **custom_payload}

    @staticmethod
    def _clean_symbol(symbol: str) -> str:
        return symbol.replace("/", "_").replace(":", "_")


def _int_or_none(value: object | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _str_or_none(value: object | None) -> str | None:
    if value is None or value == "":
        return None
    return str(value)
