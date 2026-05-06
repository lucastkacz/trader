"""Data-loading helpers for pair stress filtering."""

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.core.logger import logger
from src.data.storage.local_parquet import ParquetStorage
from src.engine.trader.runtime.pairs import extract_pair_artifact_pairs


def load_candidate_pairs(
    pairs_path: str | Path,
    timeframe: str,
    exchange: str,
) -> list[dict[str, Any]]:
    path = Path(pairs_path)
    with path.open("r") as f:
        return extract_pair_artifact_pairs(
            artifact=json.load(f),
            source_path=path,
            expected_timeframe=timeframe,
            expected_exchange=exchange,
        )


def build_unified_ohlcv(
    storage: ParquetStorage,
    symbol_a: str,
    symbol_b: str,
    timeframe: str,
    exchange: str,
) -> pd.DataFrame | None:
    try:
        df_a = storage.load_ohlcv(symbol_a, timeframe, exchange=exchange)
        df_b = storage.load_ohlcv(symbol_b, timeframe, exchange=exchange)
    except Exception as exc:
        logger.warning(f"Failed loading parquet for {symbol_a}/{symbol_b}: {exc}")
        return None

    df_a = df_a.set_index("timestamp").add_prefix("A_")
    df_b = df_b.set_index("timestamp").add_prefix("B_")
    merged = df_a.join(df_b, how="inner")
    if len(merged) < 500:
        logger.warning(f"Insufficient overlap for {symbol_a}/{symbol_b}: {len(merged)} bars")
        return None
    return merged
