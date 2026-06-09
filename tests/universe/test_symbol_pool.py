import pandas as pd

from src.data.storage.local_parquet import LocalOHLCVParquetStore
from src.engine.trader.config import load_universe_config
from src.universe.symbol_pool import load_filtered_symbol_pool


def test_symbol_pool_mega_caps_use_explicit_metric_not_stored_liquidity_metric(tmp_path):
    storage = LocalOHLCVParquetStore(str(tmp_path))
    _save_quote_volume_frame(storage, "BTC", [100, 100, 100])
    _save_quote_volume_frame(storage, "ETH", [10, 10, 10_000])
    _save_quote_volume_frame(storage, "SOL", [50, 50, 50])
    universe_cfg = _universe_config(
        stored_metric="median_quote_volume",
        mega_metric="mean_quote_volume",
    )

    pool = load_filtered_symbol_pool(
        storage=storage,
        timeframe="1m",
        exchange="bybit",
        universe_cfg=universe_cfg,
    )

    assert pool is not None
    assert set(pool) == {"BTC", "SOL"}


def _universe_config(*, stored_metric: str, mega_metric: str):
    universe_cfg = load_universe_config("configs/universe/dev.yml")
    filters = universe_cfg.filters
    stored_liquidity = filters.stored_data_liquidity.model_copy(
        update={
            "timeframe": "1m",
            "lookback_bars": 3,
            "metric": stored_metric,
            "min_value": 1,
            "percentile": None,
        }
    )
    mega_caps = filters.mega_caps.model_copy(
        update={
            "timeframe": "1m",
            "lookback_bars": 3,
            "metric": mega_metric,
            "exclude_top_n": 1,
        }
    )
    data_maturity = filters.data_maturity.model_copy(update={"min_bars": 3})
    return universe_cfg.model_copy(
        update={
            "filters": filters.model_copy(
                update={
                    "stored_data_liquidity": stored_liquidity,
                    "mega_caps": mega_caps,
                    "data_maturity": data_maturity,
                }
            )
        }
    )


def _save_quote_volume_frame(
    storage: LocalOHLCVParquetStore,
    symbol: str,
    quote_volumes: list[float],
) -> None:
    frame = pd.DataFrame(
        {
            "timestamp": [60_000 * index for index in range(len(quote_volumes))],
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
        {"coverage_status": "COMPLETE"},
        exchange="bybit",
    )
