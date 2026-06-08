"""
Tests for the unified Exchange Client.
Mocks CCXT to verify data flow without network access.
"""

import pytest
import ccxt.async_support as ccxt
from unittest.mock import AsyncMock

from src.exchange.data.ccxt_adapter import CcxtMarketDataAdapter
from src.exchange.config.venue import (
    load_ccxt_exchange_config,
    load_exchange_venue_config,
)
from src.exchange.data.market_data import (
    create_configured_ccxt_exchange,
    fetch_funding_rate_history,
    fetch_klines,
    fetch_market_tickers,
)

DEV_VENUE_CONFIG = "configs/exchange/venues/dev.yml"
DEV_MARKET_PROFILE_CONFIG = "configs/exchange/market_profiles/linear_usdt_swap.yml"
SPOT_MARKET_PROFILE_CONFIG = "configs/exchange/market_profiles/spot.yml"


def _dev_venue_config():
    return load_exchange_venue_config(DEV_VENUE_CONFIG)


def _exchange_config(path: str | None = None):
    if path is None:
        path = DEV_MARKET_PROFILE_CONFIG
    return load_ccxt_exchange_config(path)


def test_create_configured_ccxt_exchange_valid():
    """Valid CCXT exchange ID should return an exchange instance."""
    _announce(
        "Creates a configured CCXT exchange client from the dev pipeline market "
        "profile and confirms CCXT options match typed config."
    )
    venue_config = _dev_venue_config()
    exchange_config = _exchange_config()
    exchange = create_configured_ccxt_exchange(
        venue_config.exchange_id,
        "test_key",
        "test_secret",
        exchange_config,
    )
    contract = exchange_config.market_contract
    assert exchange is not None
    assert exchange.apiKey == "test_key"
    assert exchange.options.get("defaultType") == contract.default_type
    assert exchange.options.get("defaultSubType") == contract.default_sub_type
    assert exchange.options.get("defaultSettle") == contract.default_settle
    assert (
        exchange.options["adjustForTimeDifference"]
        is exchange_config.adjust_for_time_difference
    )
    assert exchange.options["recvWindow"] == exchange_config.recv_window
    assert exchange.options["fetchMarkets"]["types"] == contract.fetch_market_types


def test_create_configured_ccxt_exchange_invalid():
    """Invalid exchange ID should raise ValueError."""
    _announce(
        "Attempts to create an unknown CCXT exchange and confirms the factory "
        "raises a clear ValueError."
    )
    with pytest.raises(ValueError, match="Unknown CCXT exchange ID"):
        create_configured_ccxt_exchange(
            "nonexistent_exchange_xyz",
            "key",
            "secret",
            _exchange_config(),
        )


@pytest.mark.asyncio
async def test_fetch_market_tickers_filters_by_configured_market_profile():
    """Exchange ticker fetch should return facts for configured markets only."""
    _announce(
        "Uses mocked tickers to confirm fetch_market_tickers keeps configured "
        "dev-profile markets and leaves volume filtering to universe policy."
    )
    exchange_config = _exchange_config()
    mock_exchange = AsyncMock()
    mock_exchange.id = _dev_venue_config().exchange_id
    mock_exchange.load_markets.return_value = {
        "BTC/USDT:USDT": _matching_market(exchange_config),
        "ETH/USDT:USDT": _matching_market(exchange_config),
        "DEAD/USDT:USDT": _matching_market(exchange_config),
        "BTC/USDC:USDC": _wrong_settle_market(exchange_config),
        "BTC/USDT": {"type": "spot", "spot": True},
    }
    mock_exchange.fetch_tickers.return_value = {
        "BTC/USDT:USDT": {
            "symbol": "BTC/USDT:USDT",
            "quoteVolume": 200_000_000,
        },
        "ETH/USDT:USDT": {
            "symbol": "ETH/USDT:USDT",
            "quoteVolume": 100_000_000,
        },
        "DEAD/USDT:USDT": {
            "symbol": "DEAD/USDT:USDT",
            "quoteVolume": 500,
        },
        "BTC/USDC:USDC": {
            "symbol": "BTC/USDC:USDC",
            "quoteVolume": 300_000_000,
        },
        "BTC/USDT": {"symbol": "BTC/USDT", "quoteVolume": 400_000_000},
    }

    tickers = await fetch_market_tickers(
        mock_exchange,
        exchange_config=exchange_config,
    )

    assert [ticker.symbol for ticker in tickers] == [
        "BTC/USDT:USDT",
        "ETH/USDT:USDT",
        "DEAD/USDT:USDT",
    ]
    assert [ticker.quote_volume for ticker in tickers] == [
        200_000_000,
        100_000_000,
        500,
    ]
    assert all(ticker.market_type == "swap" for ticker in tickers)
    assert all(ticker.market_sub_type == "linear" for ticker in tickers)
    assert all(ticker.settle == "USDT" for ticker in tickers)


@pytest.mark.asyncio
async def test_fetch_market_tickers_uses_configured_spot_contract():
    _announce(
        "Switches the market profile to spot and confirms fetch_market_tickers "
        "returns the spot symbol instead of the swap symbol."
    )
    mock_exchange = AsyncMock()
    mock_exchange.id = _dev_venue_config().exchange_id
    mock_exchange.load_markets.return_value = {
        "BTC/USDT:USDT": {
            "type": "swap",
            "linear": True,
            "settle": "USDT",
        },
        "BTC/USDT": {"type": "spot", "spot": True},
    }
    mock_exchange.fetch_tickers.return_value = {
        "BTC/USDT:USDT": {
            "symbol": "BTC/USDT:USDT",
            "quoteVolume": 500_000_000,
        },
        "BTC/USDT": {"symbol": "BTC/USDT", "quoteVolume": 500_000_000},
    }

    tickers = await fetch_market_tickers(
        mock_exchange,
        exchange_config=_exchange_config(SPOT_MARKET_PROFILE_CONFIG),
    )

    assert [ticker.symbol for ticker in tickers] == ["BTC/USDT"]


@pytest.mark.asyncio
async def test_fetch_klines_network_failure():
    """Network error should be caught and re-raised as RuntimeError."""
    _announce(
        "Simulates a CCXT network failure while fetching OHLCV and confirms it is "
        "wrapped as a RuntimeError."
    )
    mock_exchange = AsyncMock()
    mock_exchange.id = "bybit"
    mock_exchange.fetch_ohlcv.side_effect = ccxt.NetworkError("502 Bad Gateway")

    with pytest.raises(RuntimeError, match="NetworkError"):
        await fetch_klines(
            exchange=mock_exchange,
            symbol="BTC/USDT:USDT",
            timeframe="4h",
            limit=100,
        )


@pytest.mark.asyncio
async def test_fetch_klines_preserves_ccxt_symbol():
    _announce(
        "Fetches mocked OHLCV and confirms the native CCXT symbol is passed "
        "through unchanged."
    )
    mock_exchange = AsyncMock()
    mock_exchange.id = "bybit"
    mock_exchange.fetch_ohlcv.return_value = [
        [1600000000000, 100.0, 101.0, 99.0, 100.5, 1000.0],
    ]

    df = await fetch_klines(
        exchange=mock_exchange,
        symbol="BTC/USDT:USDT",
        timeframe="4h",
        limit=100,
    )

    mock_exchange.fetch_ohlcv.assert_awaited_once_with(
        "BTC/USDT:USDT",
        "4h",
        limit=100,
        since=None,
    )
    assert df["close"].iloc[0] == 100.5
    assert df["timestamp"].iloc[0] == 1600000000000


@pytest.mark.asyncio
async def test_fetch_klines_applies_requested_window_after_exchange_fetch():
    _announce(
        "Fetches mocked OHLCV and confirms the requested since/end window filters "
        "the returned candles."
    )
    mock_exchange = AsyncMock()
    mock_exchange.id = "bybit"
    mock_exchange.fetch_ohlcv.return_value = [
        [1600000000000, 100.0, 101.0, 99.0, 100.5, 1000.0],
        [1600000060000, 101.0, 102.0, 100.0, 101.5, 1000.0],
        [1600000120000, 102.0, 103.0, 101.0, 102.5, 1000.0],
    ]

    df = await fetch_klines(
        exchange=mock_exchange,
        symbol="BTC/USDT:USDT",
        timeframe="1m",
        limit=100,
        since=1600000060000,
        end_ts=1600000060000,
    )

    mock_exchange.fetch_ohlcv.assert_awaited_once_with(
        "BTC/USDT:USDT",
        "1m",
        limit=100,
        since=1600000060000,
    )
    assert df["timestamp"].tolist() == [1600000060000]


@pytest.mark.asyncio
async def test_ccxt_market_data_adapter_uses_injected_exchange_without_owning_close():
    _announce(
        "Injects a mocked exchange into CcxtMarketDataAdapter and confirms the "
        "adapter does not close an exchange it does not own."
    )
    mock_exchange = AsyncMock()
    mock_exchange.id = "bybit"
    mock_exchange.fetch_ohlcv.return_value = [
        [1600000000000, 100.0, 101.0, 99.0, 100.5, 1000.0],
    ]
    adapter = CcxtMarketDataAdapter(
        "bybit",
        "key",
        "secret",
        _exchange_config(),
        exchange=mock_exchange,
    )

    df = await adapter.fetch_ohlcv("BTC/USDT:USDT", "1m", 5)
    await adapter.close()

    assert df["timestamp"].tolist() == [1600000000000]
    mock_exchange.fetch_ohlcv.assert_awaited_once()
    mock_exchange.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_funding_rate_history_success():
    """Should fetch and normalize funding rate history correctly."""
    _announce("Fetches mocked historical funding rates and verifies normalization.")
    mock_exchange = AsyncMock()
    mock_exchange.id = "bybit"
    mock_exchange.has = {"fetchFundingRateHistory": True}
    mock_exchange.fetch_funding_rate_history.return_value = [
        {"timestamp": 1600000000000, "fundingRate": 0.0001, "datetime": "2020-09-13T12:00:00.000Z"},
        {"timestamp": 1600000060000, "fundingRate": -0.0002, "datetime": "2020-09-13T12:01:00.000Z"},
    ]

    df = await fetch_funding_rate_history(
        exchange=mock_exchange,
        symbol="BTC/USDT:USDT",
        since=1600000000000,
        limit=10,
    )

    mock_exchange.fetch_funding_rate_history.assert_awaited_once_with(
        "BTC/USDT:USDT",
        since=1600000000000,
        limit=10,
    )
    assert len(df) == 2
    assert df["timestamp"].tolist() == [1600000000000, 1600000060000]
    assert df["funding_rate"].tolist() == [0.0001, -0.0002]


@pytest.mark.asyncio
async def test_fetch_funding_rate_history_normalizes_messy_provider_rows():
    """Funding history normalization should tolerate common CCXT payload noise."""
    _announce(
        "Feeds out-of-order funding rows with stale, duplicate, and malformed "
        "provider payloads and verifies canonical typed output."
    )
    mock_exchange = AsyncMock()
    mock_exchange.id = "bybit"
    mock_exchange.has = {"fetchFundingRateHistory": True}
    mock_exchange.fetch_funding_rate_history.return_value = [
        {"timestamp": 1599999940000, "fundingRate": 0.5},
        {"timestamp": 1600000060000, "fundingRate": "0.0002"},
        {"timestamp": None, "fundingRate": 0.0003},
        {"timestamp": 1600000000000, "fundingRate": "bad"},
        {"timestamp": 1600000060000, "fundingRate": -0.0002},
        {"timestamp": 1600000120000, "fundingRate": None},
    ]

    df = await fetch_funding_rate_history(
        exchange=mock_exchange,
        symbol="BTC/USDT:USDT",
        since=1600000000000,
        limit=10,
    )

    assert df["timestamp"].tolist() == [1600000060000]
    assert df["funding_rate"].tolist() == [-0.0002]
    assert str(df["timestamp"].dtype) == "int64"
    assert str(df["funding_rate"].dtype) == "float64"


@pytest.mark.asyncio
async def test_fetch_funding_rate_history_returns_typed_empty_frame():
    """Empty or filtered funding responses should preserve the canonical columns."""
    _announce(
        "Checks that funding history returns a typed empty DataFrame when all "
        "provider rows are older than the requested since timestamp."
    )
    mock_exchange = AsyncMock()
    mock_exchange.id = "bybit"
    mock_exchange.has = {"fetchFundingRateHistory": True}
    mock_exchange.fetch_funding_rate_history.return_value = [
        {"timestamp": 1599999940000, "fundingRate": 0.0001},
    ]

    df = await fetch_funding_rate_history(
        exchange=mock_exchange,
        symbol="BTC/USDT:USDT",
        since=1600000000000,
    )

    assert df.empty
    assert list(df.columns) == ["timestamp", "funding_rate"]
    assert str(df["timestamp"].dtype) == "int64"
    assert str(df["funding_rate"].dtype) == "float64"


@pytest.mark.asyncio
async def test_fetch_funding_rate_history_not_supported():
    """Should raise NotImplementedError when exchange has no fetchFundingRateHistory."""
    _announce("Verifies fetch_funding_rate_history raises error for unsupported exchanges.")
    mock_exchange = AsyncMock()
    mock_exchange.id = "binance"
    mock_exchange.has = {"fetchFundingRateHistory": False}

    with pytest.raises(NotImplementedError, match="does not support fetching funding rate history"):
        await fetch_funding_rate_history(
            exchange=mock_exchange,
            symbol="BTC/USDT:USDT",
        )


@pytest.mark.asyncio
async def test_fetch_funding_rate_history_wraps_network_errors():
    """Network failures should keep exchange context in the raised error."""
    _announce("Verifies funding history network failures are wrapped for operators.")
    mock_exchange = AsyncMock()
    mock_exchange.id = "bybit"
    mock_exchange.has = {"fetchFundingRateHistory": True}
    mock_exchange.fetch_funding_rate_history.side_effect = ccxt.NetworkError(
        "temporary outage"
    )

    with pytest.raises(RuntimeError, match="NetworkError \\(bybit\\): temporary outage"):
        await fetch_funding_rate_history(
            exchange=mock_exchange,
            symbol="BTC/USDT:USDT",
        )


def _matching_market(exchange_config):
    contract = exchange_config.market_contract
    market = {}
    if contract.default_type is not None:
        market["type"] = contract.default_type
        market[contract.default_type] = True
    if contract.default_sub_type is not None:
        market["subType"] = contract.default_sub_type
        market[contract.default_sub_type] = True
    if contract.default_settle is not None:
        market["settle"] = contract.default_settle
    return market


def _wrong_settle_market(exchange_config):
    market = _matching_market(exchange_config)
    configured_settle = exchange_config.market_contract.default_settle
    market["settle"] = "USDC" if configured_settle != "USDC" else "USDT"
    return market


def _announce(message: str) -> None:
    print(f"\nTEST: {message}")
