"""Verbose live universe probe driven by typed config.

Run explicitly with:
    .venv/bin/python -m pytest tests/exchange/data/test_live_universe_probe.py -m live -s
"""

from __future__ import annotations

import pytest

from src.engine.trader.config import load_pipeline_config, load_universe_config
from src.exchange.config.venue import (
    load_ccxt_exchange_config,
    load_exchange_venue_config,
)
from src.exchange.data.ccxt_adapter import CcxtMarketDataAdapter
from src.universe.filters.market_tickers import select_symbols_by_quote_volume

PIPELINE_CONFIG = "configs/pipelines/dev.yml"
VENUE_CONFIG = "configs/exchange/venues/dev.yml"
MARKET_PROFILE_CONFIG = "configs/exchange/market_profiles/linear_usdt_swap.yml"
UNIVERSE_CONFIG = "configs/universe/dev.yml"


@pytest.mark.live
@pytest.mark.asyncio
async def test_dev_config_fetches_live_universe_from_volume_filter() -> None:
    """Print the config inputs and symbols selected by live 24h quote volume."""
    print(
        "\nTEST: Live probe that loads dev pipeline and universe config, then runs "
        "the exchange ticker fetch and universe 24h quote-volume filter."
    )
    pipeline_cfg = load_pipeline_config(PIPELINE_CONFIG)
    venue_cfg = load_exchange_venue_config(VENUE_CONFIG)
    universe_cfg = load_universe_config(UNIVERSE_CONFIG)
    exchange_cfg = load_ccxt_exchange_config(MARKET_PROFILE_CONFIG)
    min_volume = (
        universe_cfg.filters.pre_download.ticker_liquidity.min_24h_quote_volume
    )

    _print_header("LIVE UNIVERSE PROBE")
    _print_kv("pipeline config", PIPELINE_CONFIG)
    _print_kv("venue config", VENUE_CONFIG)
    _print_kv("market profile config", MARKET_PROFILE_CONFIG)
    _print_kv("pipeline name", pipeline_cfg.name)
    _print_kv("timeframe", pipeline_cfg.timeframe)
    _print_kv("exchange id", venue_cfg.exchange_id)
    _print_kv("credential tier", venue_cfg.credential_tier)
    _print_kv("universe config", UNIVERSE_CONFIG)
    _print_kv("universe name", universe_cfg.name)
    _print_kv("24h quote volume floor", f"${min_volume:,.0f}")
    _print_kv("market profile", exchange_cfg.market_contract.name)
    _print_kv("ccxt defaultType", exchange_cfg.market_contract.default_type)
    _print_kv("ccxt defaultSubType", exchange_cfg.market_contract.default_sub_type)
    _print_kv("ccxt defaultSettle", exchange_cfg.market_contract.default_settle)
    _print_kv("fetch market types", exchange_cfg.market_contract.fetch_market_types)

    print("\nAbout to run:")
    print(
        "  CcxtMarketDataAdapter.fetch_market_tickers()"
        f" -> select_symbols_by_quote_volume(min_quote_volume={min_volume:,.0f})"
    )

    async with CcxtMarketDataAdapter(
        venue_cfg.exchange_id,
        "",
        "",
        exchange_cfg,
    ) as adapter:
        tickers = await adapter.fetch_market_tickers()
        symbols = select_symbols_by_quote_volume(
            tickers,
            min_quote_volume=min_volume,
        )

    print("\nResult:")
    _print_kv("configured tickers fetched", len(tickers))
    _print_kv("symbols returned", len(symbols))
    print("first 30 symbols:")
    for index, symbol in enumerate(symbols[:30], start=1):
        print(f"  {index:>2}. {symbol}")

    assert symbols
    assert all(isinstance(symbol, str) and symbol for symbol in symbols)


def _print_header(title: str) -> None:
    print(f"\n=== {title} ===")


def _print_kv(label: str, value: object) -> None:
    print(f"{label:<26} {value}")
