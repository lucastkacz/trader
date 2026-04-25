"""
Tests for Ghost Trader Interactive Overrides.
Specifically isolates the process_user_commands from the polling infinite loop
to prove robust state mutations offline.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock, AsyncMock

from src.engine.ghost.live_trader import LiveGhostTrader
from src.engine.ghost.state_manager import GhostStateManager
from src.core.notifier import TelegramNotifier

@pytest.fixture
def memory_state():
    mgr = GhostStateManager(db_path=":memory:")
    yield mgr
    mgr.close()

@pytest.fixture
def mock_notifier():
    notifier = TelegramNotifier()
    notifier.send = AsyncMock() # mock the async wrapper natively
    return notifier

@pytest.fixture
def live_trader():
    return LiveGhostTrader()

@pytest.mark.asyncio
async def test_pause_resume_state(live_trader, memory_state, mock_notifier):
    """Parsing /pause and /resume should successfully manipulate the global SYSTEM_PAUSED boolean."""
    memory_state.write_command("/pause")
    
    import src.engine.ghost.live_trader as live_trader_module
    
    await live_trader.process_user_commands(memory_state, pairs=[], notifier=mock_notifier, timeframe="4h")
    assert live_trader_module.SYSTEM_PAUSED is True
    
    memory_state.write_command("/resume")
    await live_trader.process_user_commands(memory_state, pairs=[], notifier=mock_notifier, timeframe="4h")
    assert live_trader_module.SYSTEM_PAUSED is False

@pytest.mark.asyncio
async def test_execute_emergency_liquidation(live_trader, memory_state, mock_notifier):
    """Proves emergency liquidation fetches live prices via mocked API and closes only the requested pair."""
    # Open dummy positions
    memory_state.open_position("BTC|ETH", "BTC", "ETH", "LONG_SPREAD", 50000, 2500, 0.5, 0.5, -2.5, 14)
    memory_state.open_position("SOL|ADA", "SOL", "ADA", "SHORT_SPREAD", 100, 0.5, 0.5, 0.5, 2.5, 14)
    
    # Mock the live fetcher!
    with patch("src.engine.ghost.live_trader.fetch_live_klines", new_callable=AsyncMock) as mock_fetch:
        # Create a tiny mock dataframe
        mock_df = pd.DataFrame({'close': [60000]}) 
        mock_fetch.return_value = mock_df
        
        # Test 1: Liquidate ONLY SOL|ADA natively
        await live_trader.execute_emergency_liquidation(memory_state, pairs=[], notifier=mock_notifier, timeframe="4h", target="SOL|ADA")
        
        open_pos = memory_state.get_open_positions()
        assert len(open_pos) == 1
        assert open_pos[0]["pair_label"] == "BTC|ETH" # Still survived!
        
        # Test 2: Liquidate ALL remaining
        await live_trader.execute_emergency_liquidation(memory_state, pairs=[], notifier=mock_notifier, timeframe="4h", target=None)
        
        open_pos = memory_state.get_open_positions()
        assert len(open_pos) == 0 # Everything liquidated
        
        # Verify network was mocked appropriately (Called 4 times: [SOL, ADA] + [BTC, ETH])
        assert mock_fetch.call_count == 4
