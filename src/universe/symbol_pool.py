"""Universe loading helpers for research discovery."""

from pathlib import Path

import pandas as pd

from src.core.logger import logger
from src.data.storage.local_parquet import LocalOHLCVParquetStore
from src.engine.trader.config import UniverseConfig
from src.universe.filters.data_maturity import DataMaturityFilter
from src.universe.filters.mega_caps import exclude_top_by_quote_volume_metric
from src.universe.filters.ohlcv_liquidity import select_by_quote_volume_metric


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
    liquidity_cfg = filters_cfg.stored_data_liquidity
    if liquidity_cfg.enabled:
        _require_matching_timeframe(
            configured_timeframe=liquidity_cfg.timeframe,
            loaded_timeframe=timeframe,
            filter_name="stored_data_liquidity",
        )
        liquidity = select_by_quote_volume_metric(
            frames,
            lookback_bars=liquidity_cfg.lookback_bars,
            metric=liquidity_cfg.metric,
            min_value=liquidity_cfg.min_value,
            percentile=liquidity_cfg.percentile,
        )
        pool = liquidity.pool
    else:
        pool = frames

    mega_cfg = filters_cfg.mega_caps
    if mega_cfg.exclude_top_n > 0:
        _require_matching_timeframe(
            configured_timeframe=mega_cfg.timeframe,
            loaded_timeframe=timeframe,
            filter_name="mega_caps",
        )
        pool = exclude_top_by_quote_volume_metric(
            pool,
            lookback_bars=mega_cfg.lookback_bars,
            metric=mega_cfg.metric,
            exclude_top_n=mega_cfg.exclude_top_n,
        )
    logger.info(f"Loaded {len(pool)} assets into RAM memory safely.")
    return _select_mature_pool(pool, filters_cfg.data_maturity.min_bars)


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


def _require_matching_timeframe(
    *,
    configured_timeframe: str,
    loaded_timeframe: str,
    filter_name: str,
) -> None:
    if configured_timeframe != loaded_timeframe:
        raise ValueError(
            f"{filter_name}.timeframe={configured_timeframe!r} must match loaded "
            f"parquet timeframe {loaded_timeframe!r}"
        )
