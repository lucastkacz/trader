"""Universe loading helpers for research discovery."""

from pathlib import Path

import pandas as pd

from src.core.logger import logger
from src.data.storage.local_parquet import LocalOHLCVParquetStore
from src.engine.trader.config import UniverseConfig
from src.universe.filters.data_quality import metadata_passes_quality


def load_filtered_symbol_pool(
    storage: LocalOHLCVParquetStore,
    timeframe: str,
    exchange: str,
    universe_cfg: UniverseConfig,
) -> dict[str, pd.DataFrame] | None:
    base_path = Path(storage.base_dir) / exchange / timeframe
    if not base_path.exists():
        logger.error(f"Cannot find populated parquet directory at {base_path}")
        return None

    files = [path for path in base_path.iterdir() if path.suffix == ".parquet"]
    logger.info(f"Detected {len(files)} historical datasets.")

    quality_cfg = universe_cfg.filters.post_download.data_quality
    pool = _load_symbol_frames(
        storage,
        files,
        timeframe,
        exchange,
        quality_cfg=quality_cfg,
    )
    logger.info(f"Loaded {len(pool)} assets into RAM memory safely.")
    return pool


def _load_symbol_frames(
    storage: LocalOHLCVParquetStore,
    files: list[Path],
    timeframe: str,
    exchange: str,
    quality_cfg,
) -> dict[str, pd.DataFrame]:
    frames = {}
    rejected_count = 0
    for path in files:
        symbol = path.stem.replace("_", "/")
        if "USDC" in symbol:
            continue
        metadata = storage.read_ohlcv_metadata(symbol, timeframe, exchange=exchange)
        if not metadata_passes_quality(
            metadata,
            require_coverage_status=quality_cfg.require_coverage_status,
            require_quality_status=quality_cfg.require_quality_status,
            max_missing_candles=quality_cfg.max_missing_candles,
            max_gap_count=quality_cfg.max_gap_count,
        ):
            rejected_count += 1
            continue
        try:
            df = storage.load_ohlcv(symbol, timeframe, exchange=exchange)
            df.set_index("timestamp", inplace=True)
        except Exception as exc:
            logger.warning(f"Failed loading {symbol}: {exc}")
            continue
        frames[symbol] = df
    logger.info(
        f"Post-download data quality filter rejected {rejected_count} datasets."
    )
    return frames
