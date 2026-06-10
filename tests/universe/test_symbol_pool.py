import pandas as pd

from src.data.storage.local_parquet import LocalOHLCVParquetStore
from src.engine.trader.config import load_universe_config
from src.universe.symbol_pool import load_filtered_symbol_pool


def test_symbol_pool_keeps_only_complete_validated_post_download_data(tmp_path):
    storage = LocalOHLCVParquetStore(str(tmp_path))
    base_ts = 1_600_000_000_000
    _save_quote_volume_frame(storage, "VALID", [100, 100, 100], base_ts=base_ts)
    _save_quote_volume_frame(
        storage,
        "GAPPY",
        [100, 100],
        timestamps=[base_ts, base_ts + 120_000],
    )
    _save_quote_volume_frame(
        storage,
        "INCOMPLETE",
        [100, 100, 100],
        coverage_status="INCOMPLETE",
        base_ts=base_ts,
    )
    universe_cfg = load_universe_config("configs/universe/dev.yml")

    pool = load_filtered_symbol_pool(
        storage=storage,
        timeframe="1m",
        exchange="bybit",
        universe_cfg=universe_cfg,
    )

    assert pool is not None
    assert set(pool) == {"VALID"}


def _save_quote_volume_frame(
    storage: LocalOHLCVParquetStore,
    symbol: str,
    quote_volumes: list[float],
    *,
    coverage_status: str = "COMPLETE",
    timestamps: list[int] | None = None,
    base_ts: int = 1_600_000_000_000,
) -> None:
    timestamps = timestamps or [
        base_ts + 60_000 * index for index in range(len(quote_volumes))
    ]
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [1.0] * len(quote_volumes),
            "high": [1.0] * len(quote_volumes),
            "low": [1.0] * len(quote_volumes),
            "close": [1.0] * len(quote_volumes),
            "volume": quote_volumes,
        }
    )
    storage.save_ohlcv(
        symbol,
        "1m",
        frame,
        {"coverage_status": coverage_status},
        exchange="bybit",
    )
