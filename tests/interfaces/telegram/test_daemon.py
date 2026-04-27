from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.config import settings
from src.engine.trader.state_manager import TradeStateManager
from src.interfaces.telegram import daemon


class FakeUpdate:
    def __init__(self, chat_id: str):
        self.effective_chat = SimpleNamespace(id=chat_id)
        self.message = SimpleNamespace(reply_text=AsyncMock())


@pytest.fixture
def configured_daemon(tmp_path):
    db_path = tmp_path / "trader.db"
    cfg_path = tmp_path / "telegram.yml"
    cfg_path.write_text(
        "telegram:\n"
        "  environment: TEST\n"
        "  bot_name: '@TestBot'\n"
        f"  db_path: '{db_path}'\n"
    )

    settings.telegram_chat_id = "123"
    daemon.configure_daemon(str(cfg_path))
    yield db_path
    daemon.TELEGRAM_DB_PATH = None
    daemon.TELEGRAM_ENVIRONMENT = "UNKNOWN"


def _context(args=None):
    return SimpleNamespace(args=args or [])


@pytest.mark.asyncio
async def test_status_reads_configured_database(configured_daemon):
    state = TradeStateManager(db_path=str(configured_daemon))
    try:
        state.open_position("BTC|ETH", "BTC", "ETH", "LONG_SPREAD", 100.0, 50.0, 0.5, 0.5, -2.0, 14)
        state.snapshot_equity(
            total_equity_pct=0.03,
            open_positions=1,
            realized_pnl_pct=0.01,
            unrealized_pnl_pct=0.02,
        )
    finally:
        state.close()

    update = FakeUpdate(chat_id="123")
    await daemon.bot_status(update, _context())

    update.message.reply_text.assert_awaited_once()
    message = update.message.reply_text.await_args.args[0]
    assert "TRADER STATUS" in message
    assert "Mode: TEST" in message
    assert "Realized: 1.00%" in message
    assert "Open Spreads:</b> 1" in message


@pytest.mark.asyncio
async def test_pause_resume_write_commands_to_configured_database(configured_daemon):
    update = FakeUpdate(chat_id="123")

    await daemon.bot_pause(update, _context())
    await daemon.bot_resume(update, _context())

    state = TradeStateManager(db_path=str(configured_daemon))
    try:
        commands = state.get_commands()
    finally:
        state.close()

    assert [cmd["command"] for cmd in commands] == ["/pause", "/resume"]
    assert [cmd["status"] for cmd in commands] == ["PENDING", "PENDING"]


@pytest.mark.asyncio
async def test_stop_all_writes_command_to_configured_database(configured_daemon):
    update = FakeUpdate(chat_id="123")

    await daemon.bot_stop_all(update, _context())

    state = TradeStateManager(db_path=str(configured_daemon))
    try:
        commands = state.get_commands()
    finally:
        state.close()

    assert len(commands) == 1
    assert commands[0]["command"] == "/stop_all"
    assert commands[0]["target_pair"] is None


@pytest.mark.asyncio
async def test_unauthorized_chat_is_rejected(configured_daemon):
    update = FakeUpdate(chat_id="999")

    await daemon.bot_pause(update, _context())

    update.message.reply_text.assert_not_awaited()
    state = TradeStateManager(db_path=str(configured_daemon))
    try:
        commands = state.get_commands()
    finally:
        state.close()

    assert commands == []
