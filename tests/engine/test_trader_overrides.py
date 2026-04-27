"""
Tests for Trader Interactive Overrides.
Specifically isolates the process_user_commands from the polling infinite loop
to prove robust state mutations offline.
"""

import pytest
import pandas as pd
from unittest.mock import patch, AsyncMock

from src.engine.trader.live_trader import LiveTrader
from src.engine.trader.state_manager import TradeStateManager
from src.interfaces.telegram.notifier import TelegramNotifier

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
def live_trader():
    return LiveTrader()

@pytest.mark.asyncio
async def test_pause_resume_state(live_trader, memory_state, mock_notifier):
    """Parsing /pause and /resume should persist durable runtime pause state."""
    memory_state.write_command("/pause")
    
    await live_trader.process_user_commands(memory_state, pairs=[], notifier=mock_notifier, timeframe="4h", exchange_id="bybit", api_key="", api_secret="")
    assert memory_state.is_system_paused() is True
    assert memory_state.get_commands()[0]["status"] == "EXECUTED"
    
    memory_state.write_command("/resume")
    await live_trader.process_user_commands(memory_state, pairs=[], notifier=mock_notifier, timeframe="4h", exchange_id="bybit", api_key="", api_secret="")
    assert memory_state.is_system_paused() is False
    assert memory_state.get_commands()[1]["status"] == "EXECUTED"

@pytest.mark.asyncio
async def test_unknown_command_is_marked_ignored(live_trader, memory_state, mock_notifier):
    """Unknown commands should become IGNORED instead of disappearing."""
    memory_state.write_command("/mystery")

    await live_trader.process_user_commands(memory_state, pairs=[], notifier=mock_notifier, timeframe="4h", exchange_id="bybit", api_key="", api_secret="")

    command = memory_state.get_commands()[0]
    assert command["status"] == "IGNORED"
    assert command["error"] == "unknown command"

@pytest.mark.asyncio
async def test_paused_tick_skips_execution(live_trader, memory_state, mock_notifier):
    """A paused trader should return before writing tick-derived state."""
    memory_state.set_system_paused(True)

    await live_trader.execute_tick(
        pairs=[],
        state=memory_state,
        notifier=mock_notifier,
        timeframe="4h",
        strategy_cfg={"execution": {"volatility_lookback_bars": 60, "exit_z_score": 0.0}},
        exchange_id="bybit",
        api_key="",
        api_secret="",
    )

    assert memory_state.get_equity_curve() == []

@pytest.mark.asyncio
async def test_execute_emergency_liquidation(live_trader, memory_state, mock_notifier):
    """Proves emergency liquidation fetches live prices via mocked API and closes only the requested pair."""
    # Open dummy positions
    memory_state.open_position("BTC|ETH", "BTC", "ETH", "LONG_SPREAD", 50000, 2500, 0.5, 0.5, -2.5, 14)
    memory_state.open_position("SOL|ADA", "SOL", "ADA", "SHORT_SPREAD", 100, 0.5, 0.5, 0.5, 2.5, 14)
    
    # Mock the live fetcher!
    with patch("src.engine.trader.live_trader.fetch_live_klines", new_callable=AsyncMock) as mock_fetch:
        # Create a tiny mock dataframe
        mock_df = pd.DataFrame({'close': [60000]}) 
        mock_fetch.return_value = mock_df
        
        # Test 1: Liquidate ONLY SOL|ADA natively
        await live_trader.execute_emergency_liquidation(memory_state, pairs=[], notifier=mock_notifier, timeframe="4h", exchange_id="bybit", api_key="", api_secret="", target="SOL|ADA")
        
        open_pos = memory_state.get_open_positions()
        assert len(open_pos) == 1
        assert open_pos[0]["pair_label"] == "BTC|ETH" # Still survived!
        
        # Test 2: Liquidate ALL remaining
        await live_trader.execute_emergency_liquidation(memory_state, pairs=[], notifier=mock_notifier, timeframe="4h", exchange_id="bybit", api_key="", api_secret="", target=None)
        
        open_pos = memory_state.get_open_positions()
        assert len(open_pos) == 0 # Everything liquidated
        
        # Verify network was mocked appropriately (Called 4 times: [SOL, ADA] + [BTC, ETH])
        assert mock_fetch.call_count == 4
