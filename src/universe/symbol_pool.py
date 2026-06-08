"""Universe loading helpers for research discovery."""

from pathlib import Path

import pandas as pd

from src.core.logger import logger
from src.data.storage.local_parquet import LocalOHLCVParquetStore
from src.engine.trader.config import UniverseConfig
from src.universe.filters.data_maturity import DataMaturityFilter
from src.universe.filters.mega_caps import exclude_top_by_dollar_volume
from src.universe.filters.ohlcv_liquidity import select_by_average_dollar_volume


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

    filters_cfg = universe_cfg.filters
    frames = _load_symbol_frames(storage, files, timeframe, exchange)
    liquidity = select_by_average_dollar_volume(
        frames,
        lookback_bars=filters_cfg.volume_lookback_bars,
        min_dollar_volume=filters_cfg.min_volume_liquidity,
        max_dollar_volume=filters_cfg.max_volume_liquidity,
    )
    pool = exclude_top_by_dollar_volume(
        liquidity.pool,
        liquidity.dollar_volumes,
        exclude_top_n=filters_cfg.exclude_top_n_mega_caps,
    )
    logger.info(f"Loaded {len(pool)} assets into RAM memory safely.")
    return _select_mature_pool(pool, filters_cfg.min_data_maturity_bars)


def _load_symbol_frames(
    storage: LocalOHLCVParquetStore,
    files: list[Path],
    timeframe: str,
    exchange: str,
) -> dict[str, pd.DataFrame]:
    frames = {}
    for path in files:
        symbol = path.stem.replace("_", "/")
        if "USDC" in symbol:
            continue
        try:
            df = storage.load_ohlcv(symbol, timeframe, exchange=exchange)
            df.set_index("timestamp", inplace=True)
        except Exception as exc:
            logger.warning(f"Failed loading {symbol}: {exc}")
            continue
        frames[symbol] = df
    return frames


def _select_mature_pool(
    pool: dict[str, pd.DataFrame],
    min_bars: int,
) -> dict[str, pd.DataFrame]:
    sieve = DataMaturityFilter(min_bars=min_bars)
    surviving_symbols = sieve.filter(pool)
    return {symbol: pool[symbol] for symbol in surviving_symbols}
