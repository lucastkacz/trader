"""
Tests for TelegramNotifier.
Strictly verifies asynchronous safety and network-failure catch blocks.
"""

import pytest
import requests
from unittest.mock import patch, MagicMock

from src.core.config import settings
from src.interfaces.telegram.notifier import TelegramNotifier


@pytest.fixture
def notifier():
    """Returns a notifier with mock credentials."""
    settings.telegram_bot_token = "mock_token"
    settings.telegram_chat_id = "mock_chat_id"
    settings.log_level = "debug"
    return TelegramNotifier()


def test_notifier_requests_success(notifier):
    """Proves the synchronous requests payload is correctly constructed."""
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        notifier._send_sync("Test message")
        
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        
        # Verify strict network timeout! Must not exceed 2.0
        assert kwargs["timeout"] <= 2.0
        
        # Verify payloads
        assert "botmock_token/sendMessage" in args[0]
        assert kwargs["json"]["chat_id"] == "mock_chat_id"
        assert "Test message" in kwargs["json"]["text"]
        assert "[TRADER PAPER]" in kwargs["json"]["text"]


def test_notifier_network_hang(notifier):
    """Proves that a catastrophic Telegram API drop does not crash the system."""
    with patch("requests.post", side_effect=requests.exceptions.Timeout("Connection timed out")):
        # If this raises, the test fails. It should swallow it gracefully.
        notifier._send_sync("Test hang")
        
    # The pure execution of this block without raising a requests.exceptions.Timeout 
    # proves mathematical isolation of the network bridge!


@pytest.mark.asyncio
async def test_notifier_async_send(notifier):
    """Proves the async wrapper delegates via the background executor seamlessly."""
    with patch.object(notifier, "_send_sync") as mock_sync:
        await notifier.send("Async message")
        mock_sync.assert_called_once_with("Async message")
