"""
Tests for Trader Interactive Overrides.
Specifically isolates the process_user_commands from the polling infinite loop
to prove robust state mutations offline.
"""

import pytest
import pandas as pd
from unittest.mock import patch, AsyncMock

from src.exchange.config.venue import load_ccxt_exchange_config
from src.engine.trader.commands.processor import process_user_commands
from src.engine.trader.config import OrderExecutionConfig, load_strategy_config
from src.engine.trader.execution.liquidation import execute_emergency_liquidation
from src.engine.trader.execution.market_data import ReadonlyMarketDataFetchPolicy
from src.engine.trader.runtime.tick import execute_tick
from src.engine.trader.state.manager import TradeStateManager
from src.interfaces.telegram.notifier import TelegramNotifier


def _exchange_config():
    return load_ccxt_exchange_config("configs/exchange/market_profiles/linear_usdt_swap.yml")


@pytest.fixture
def memory_state():
    mgr = TradeStateManager(db_path=":memory:")
    yield mgr
    mgr.close()

@pytest.fixture
def mock_notifier():
    notifier = TelegramNotifier()
    notifier.send = AsyncMock() # mock the async wrapper natively
    return notifier

@pytest.fixture
def state_only_order_execution():
    return OrderExecutionConfig(
        mode="state_only",
        fill_poll_attempts=0,
        fill_poll_interval_seconds=0.0,
        cancel_unfilled_after_poll=False,
        client_order_prefix="test",
    )


def _market_data_fetch_policy():
    return ReadonlyMarketDataFetchPolicy(
        request_timeout_seconds=1.0,
        max_attempts=1,
        retry_backoff_seconds=0.0,
    )


@pytest.mark.asyncio
async def test_pause_resume_state(memory_state, mock_notifier):
    """Parsing /pause and /resume should persist durable runtime pause state."""
    memory_state.write_command("/pause")
    
    await process_user_commands(memory_state, pairs=[], notifier=mock_notifier, timeframe="4h", exchange_id="bybit", api_key="", api_secret="", exchange_config=_exchange_config(), market_data_fetch_policy=_market_data_fetch_policy())
    assert memory_state.is_system_paused() is True
    assert memory_state.get_commands()[0]["status"] == "EXECUTED"
    
    memory_state.write_command("/resume")
    await process_user_commands(memory_state, pairs=[], notifier=mock_notifier, timeframe="4h", exchange_id="bybit", api_key="", api_secret="", exchange_config=_exchange_config(), market_data_fetch_policy=_market_data_fetch_policy())
    assert memory_state.is_system_paused() is False
    assert memory_state.get_commands()[1]["status"] == "EXECUTED"

@pytest.mark.asyncio
async def test_unknown_command_is_marked_ignored(memory_state, mock_notifier):
    """Unknown commands should become IGNORED instead of disappearing."""
    memory_state.write_command("/mystery")

    await process_user_commands(memory_state, pairs=[], notifier=mock_notifier, timeframe="4h", exchange_id="bybit", api_key="", api_secret="", exchange_config=_exchange_config(), market_data_fetch_policy=_market_data_fetch_policy())

    command = memory_state.get_commands()[0]
    assert command["status"] == "IGNORED"
    assert command["error"] == "unknown command"

@pytest.mark.asyncio
async def test_paused_tick_skips_execution(
    memory_state,
    mock_notifier,
    state_only_order_execution,
):
    """A paused trader should return before writing tick-derived state."""
    memory_state.set_system_paused(True)

    await execute_tick(
        pairs=[],
        state=memory_state,
        notifier=mock_notifier,
        timeframe="4h",
        strategy_cfg=load_strategy_config("configs/strategy/dev.yml"),
        exchange_id="bybit",
        api_key="",
        api_secret="",
        exchange_config=_exchange_config(),
        order_execution_cfg=state_only_order_execution,
        order_execution_adapter=None,
    )

    assert memory_state.get_equity_curve() == []

@pytest.mark.asyncio
async def test_execute_emergency_liquidation(memory_state, mock_notifier):
    """Proves emergency liquidation fetches live prices via mocked API and closes only the requested pair."""
    # Open dummy positions
    memory_state.open_position("BTC|ETH", "BTC", "ETH", "LONG_SPREAD", 50000, 2500, 0.5, 0.5, -2.5, 14)
    memory_state.open_position("SOL|ADA", "SOL", "ADA", "SHORT_SPREAD", 100, 0.5, 0.5, 0.5, 2.5, 14)
    
    with patch("src.engine.trader.execution.liquidation.fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
        # Create a tiny mock dataframe
        mock_df = pd.DataFrame({'close': [60000]}) 
        mock_fetch.return_value = mock_df
        
        # Test 1: Liquidate ONLY SOL|ADA natively
        await execute_emergency_liquidation(memory_state, pairs=[], notifier=mock_notifier, timeframe="4h", exchange_id="bybit", api_key="", api_secret="", exchange_config=_exchange_config(), market_data_fetch_policy=_market_data_fetch_policy(), target="SOL|ADA")
        
        open_pos = memory_state.get_open_positions()
        assert len(open_pos) == 1
        assert open_pos[0]["pair_label"] == "BTC|ETH" # Still survived!
        
        # Test 2: Liquidate ALL remaining
        await execute_emergency_liquidation(memory_state, pairs=[], notifier=mock_notifier, timeframe="4h", exchange_id="bybit", api_key="", api_secret="", exchange_config=_exchange_config(), market_data_fetch_policy=_market_data_fetch_policy(), target=None)
        
        open_pos = memory_state.get_open_positions()
        assert len(open_pos) == 0 # Everything liquidated
        
        # Verify network was mocked appropriately (Called 4 times: [SOL, ADA] + [BTC, ETH])
        assert mock_fetch.call_count == 4


@pytest.mark.asyncio
async def test_emergency_liquidation_is_explicit_local_state_close(
    memory_state,
    mock_notifier,
):
    """Operator stops should be recorded as forced local closes, not strategy exits."""
    spread_id = memory_state.open_position(
        "BTC|ETH",
        "BTC",
        "ETH",
        "LONG_SPREAD",
        50000,
        2500,
        0.5,
        0.5,
        -2.5,
        14,
    )

    with patch("src.engine.trader.execution.liquidation.fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = pd.DataFrame({"close": [60000]})

        await execute_emergency_liquidation(
            memory_state,
            pairs=[],
            notifier=mock_notifier,
            timeframe="4h",
            exchange_id="bybit",
            api_key="",
            api_secret="",
            exchange_config=_exchange_config(),
            market_data_fetch_policy=_market_data_fetch_policy(),
            target="BTC|ETH",
        )

    closed = memory_state.get_all_closed()
    assert closed[0]["close_reason"] == "FORCE_CLOSE_REQUESTED"
    close_events = [
        event for event in memory_state.get_order_events(spread_id=spread_id)
        if event["event_type"] == "FORCE_CLOSE_REQUESTED"
    ]
    assert len(close_events) == 1
    assert [leg["status"] for leg in memory_state.get_leg_fills(spread_id=spread_id)] == [
        "TARGET_RECORDED",
        "TARGET_RECORDED",
        "TARGET_RECORDED",
        "TARGET_RECORDED",
    ]
    sent_messages = [call.args[0] for call in mock_notifier.send.await_args_list]
    assert any("LOCAL STATE" in message for message in sent_messages)
