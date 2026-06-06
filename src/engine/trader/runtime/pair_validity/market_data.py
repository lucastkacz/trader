"""Market-data loading for read-only pair-validity diagnostics."""

from datetime import datetime

import pandas as pd

from src.data.storage.local_parquet import LocalOHLCVParquetStore
from src.engine.trader.runtime.pair_validity.time import as_utc


def load_recent_market_data(
    *,
    storage: LocalOHLCVParquetStore,
    asset_x: str,
    asset_y: str,
    timeframe: str,
    exchange: str,
) -> pd.DataFrame | None:
    """Load aligned local OHLCV closes for a promoted pair."""
    try:
        df_x = normalize_ohlcv(storage.load_ohlcv(asset_x, timeframe, exchange))
        df_y = normalize_ohlcv(storage.load_ohlcv(asset_y, timeframe, exchange))
    except (FileNotFoundError, KeyError, ValueError):
        return None

    return (
        df_x.set_index("timestamp")[["close"]]
        .rename(columns={"close": "asset_x_close"})
        .join(
            df_y.set_index("timestamp")[["close"]].rename(
                columns={"close": "asset_y_close"}
            ),
            how="inner",
        )
        .dropna()
        .sort_index()
    )


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if "timestamp" not in df.columns or "close" not in df.columns:
        raise KeyError("OHLCV data must include timestamp and close columns")
    normalized = df[["timestamp", "close"]].copy()
    timestamp = normalized["timestamp"]
    if pd.api.types.is_numeric_dtype(timestamp):
        unit = "ms" if float(timestamp.abs().max()) > 10_000_000_000 else None
        normalized["timestamp"] = pd.to_datetime(timestamp, unit=unit, utc=True)
    else:
        normalized["timestamp"] = pd.to_datetime(timestamp, utc=True)
    normalized["close"] = pd.to_numeric(normalized["close"], errors="coerce")
    return normalized.dropna(subset=["timestamp", "close"])


def latest_timestamp(market: pd.DataFrame) -> datetime | None:
    if market.empty:
        return None
    return as_utc(market.index.max().to_pydatetime())
