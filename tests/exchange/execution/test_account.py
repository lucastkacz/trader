from unittest.mock import AsyncMock

import pytest

from src.exchange.config.venue import load_ccxt_exchange_config
from src.exchange.execution.account import CCXTReadOnlySnapshotProvider


def _exchange_config():
    return load_ccxt_exchange_config("configs/exchange/market_profiles/linear_usdt_swap.yml")


def _provider(exchange: AsyncMock) -> CCXTReadOnlySnapshotProvider:
    return CCXTReadOnlySnapshotProvider(
        exchange_id="bybit",
        api_key="readonly-key",
        api_secret="readonly-secret",
        exchange_config=_exchange_config(),
        exchange_factory=lambda *_: exchange,
    )


@pytest.mark.asyncio
async def test_account_snapshot_provider_normalizes_open_positions_and_ignores_zero_rows():
    _announce(
        "Fetches mocked open positions and confirms the account snapshot provider "
        "normalizes non-zero rows while ignoring zero-sized positions."
    )
    exchange = AsyncMock()
    exchange.fetch_positions.return_value = [
        {
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "contracts": 0.6,
        },
        {
            "symbol": "ETH/USDT:USDT",
            "side": "short",
            "contracts": 0.4,
        },
        {
            "symbol": "SOL/USDT:USDT",
            "side": None,
            "contracts": 0.0,
        },
    ]

    snapshots = await _provider(exchange).fetch_open_positions()

    assert [snapshot.model_dump() for snapshot in snapshots] == [
        {
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "qty": 0.6,
            "spread_id": None,
        },
        {
            "symbol": "ETH/USDT:USDT",
            "side": "short",
            "qty": 0.4,
            "spread_id": None,
        },
    ]
    exchange.fetch_positions.assert_awaited_once_with()
    exchange.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_account_snapshot_provider_closes_exchange_after_snapshot_failure():
    _announce(
        "Simulates an account snapshot failure and confirms the provider still "
        "closes the exchange client."
    )
    exchange = AsyncMock()
    exchange.fetch_positions.side_effect = RuntimeError("account snapshot unavailable")

    with pytest.raises(RuntimeError, match="account snapshot unavailable"):
        await _provider(exchange).fetch_open_positions()

    exchange.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_account_snapshot_provider_rejects_open_position_without_side():
    _announce(
        "Returns a non-zero open position without side and confirms the provider "
        "rejects malformed exchange data."
    )
    exchange = AsyncMock()
    exchange.fetch_positions.return_value = [
        {
            "symbol": "BTC/USDT:USDT",
            "side": None,
            "contracts": 0.6,
        },
    ]

    with pytest.raises(ValueError, match="Open exchange position is missing side"):
        await _provider(exchange).fetch_open_positions()

    exchange.close.assert_awaited_once_with()


def _announce(message: str) -> None:
    print(f"\nTEST: {message}")
