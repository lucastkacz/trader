"""Universe loading helpers for research discovery."""

from pathlib import Path

import pandas as pd

from src.core.logger import logger
from src.data.storage.local_parquet import ParquetStorage
from src.engine.trader.config import UniverseConfig
from src.screener.filters.data_maturity import DataMaturityFilter


def load_filtered_symbol_pool(
    storage: ParquetStorage,
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

    pool, volumes = _load_liquid_symbols(storage, files, timeframe, exchange, universe_cfg)
    pool = _remove_mega_caps(pool, volumes, universe_cfg.filters.exclude_top_n_mega_caps)
    logger.info(f"Loaded {len(pool)} assets into RAM memory safely.")
    return _select_mature_pool(pool, universe_cfg.filters.min_data_maturity_bars)


def _load_liquid_symbols(
    storage: ParquetStorage,
    files: list[Path],
    timeframe: str,
    exchange: str,
    universe_cfg: UniverseConfig,
) -> tuple[dict[str, pd.DataFrame], dict[str, float]]:
    filters_cfg = universe_cfg.filters
    pool = {}
    volumes = {}
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

        recent_df = df.iloc[-filters_cfg.volume_lookback_bars:]
        dollar_vol = (recent_df["volume"] * recent_df["close"]).mean()
        if filters_cfg.min_volume_liquidity <= dollar_vol <= filters_cfg.max_volume_liquidity:
            volumes[symbol] = dollar_vol
            pool[symbol] = df
    return pool, volumes


def _remove_mega_caps(
    pool: dict[str, pd.DataFrame],
    volumes: dict[str, float],
    exclude_top_n: int,
) -> dict[str, pd.DataFrame]:
    sorted_symbols = sorted(volumes.keys(), key=lambda key: volumes[key], reverse=True)
    mega_caps = sorted_symbols[:exclude_top_n]
    logger.warning(f"Omitting Tier-1 Mega-Caps computationally: {mega_caps}")
    return {symbol: df for symbol, df in pool.items() if symbol not in mega_caps}


def _select_mature_pool(
    pool: dict[str, pd.DataFrame],
    min_bars: int,
) -> dict[str, pd.DataFrame]:
    sieve = DataMaturityFilter(min_bars=min_bars)
    surviving_symbols = sieve.filter(pool)
    return {symbol: pool[symbol] for symbol in surviving_symbols}
