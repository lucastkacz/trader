"""Manual live OHLCV probe for inspecting local Parquet output.

Run explicitly:
    .venv/bin/python -m pytest tests/data/test_ohlcv_live_probe.py -m live -q

Output defaults to:
    data/test/ohlcv_live_probe/bybit/1m/*.parquet
"""

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.exchange.data.ccxt_adapter import CcxtMarketDataAdapter
from src.exchange.config.venue import load_ccxt_exchange_config
from src.data.storage.local_parquet import LocalOHLCVParquetStore
from src.data.sync import (
    OHLCVFetchPolicy,
    OHLCVMarketMetadata,
    OHLCVRefreshRequest,
    OHLCVRefreshService,
)
from src.utils.timeframe_math import last_closed_candle_open_ms


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_ohlcv_probe_writes_small_1m_parquet_sample():
    print(
        "\nTEST: Live probe that refreshes a tiny BTC/ETH/XRP 1m OHLCV sample and "
        "writes local Parquet files for inspection."
    )
    output_dir = Path(
        os.environ.get("OHLCV_LIVE_PROBE_DIR", "data/test/ohlcv_live_probe")
    )
    exchange_id = "bybit"
    timeframe = "1m"
    symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT", "XRP/USDT:USDT"]
    end_ts = _closed_1m_candle_end_ms()
    store = LocalOHLCVParquetStore(str(output_dir))
    exchange_config = load_ccxt_exchange_config(
        "configs/exchange/market_profiles/linear_usdt_swap.yml"
    )

    async with CcxtMarketDataAdapter(exchange_id, "", "", exchange_config) as adapter:
        service = OHLCVRefreshService(
            market_data=adapter,
            store=store,
            policy=OHLCVFetchPolicy(
                fetch_limit=5,
                max_retries=1,
                retry_backoff_seconds=1,
                request_pause_seconds=0.2,
            ),
        )
        result = await service.run(
            OHLCVRefreshRequest(
                exchange_id=exchange_id,
                timeframe=timeframe,
                symbols=symbols,
                end_ts=end_ts,
                overlap_bars=1,
                missing_lookback_bars=5,
                market=OHLCVMarketMetadata(
                    market_type=exchange_config.market_contract.default_type,
                    market_sub_type=exchange_config.market_contract.default_sub_type,
                    settle=exchange_config.market_contract.default_settle,
                ),
            )
        )

    assert result.symbol_count == len(symbols)
    assert result.success_count >= 1
    for symbol_result in result.results:
        path = store.path_for_ohlcv(symbol_result.symbol, timeframe, exchange_id)
        metadata = store.read_ohlcv_metadata(symbol_result.symbol, timeframe, exchange_id)
        assert path.exists()
        assert metadata is not None
        assert metadata.timeframe == timeframe
        assert metadata.exchange == exchange_id
        assert metadata.market_type == "swap"
        assert metadata.market_sub_type == "linear"
        assert metadata.settle == "USDT"


def _closed_1m_candle_end_ms() -> int:
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    return last_closed_candle_open_ms("1m", now_ms=now_ms)
