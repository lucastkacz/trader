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
        "  holding_period_bar_minutes: 1\n"
    )

    settings.telegram_chat_id = "123"
    cfg = daemon.configure_daemon(str(cfg_path))
    assert cfg.environment == "TEST"
    assert cfg.db_path == str(db_path)
    yield db_path
    daemon.TELEGRAM_DB_PATH = None
    daemon.TELEGRAM_ENVIRONMENT = None
    daemon.TELEGRAM_HOLDING_PERIOD_BAR_MINUTES = None


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
async def test_positions_use_configured_holding_bar_minutes(configured_daemon):
    state = TradeStateManager(db_path=str(configured_daemon))
    try:
        state.open_position("BTC|ETH", "BTC", "ETH", "LONG_SPREAD", 100.0, 50.0, 0.5, 0.5, -2.0, 14)
    finally:
        state.close()

    update = FakeUpdate(chat_id="123")
    await daemon.bot_positions(update, _context())

    update.message.reply_text.assert_awaited_once()
    message = update.message.reply_text.await_args.args[0]
    assert "OPEN POSITIONS" in message
    assert "#1 BTC|ETH" in message
    assert "BTC|ETH" in message
    assert "Duration:" in message
    assert daemon.holding_duration_minutes({"holding_bars": 6}) == 6
    assert daemon.format_duration(6) == "6m"
    assert daemon.format_duration(240) == "4h"


@pytest.mark.asyncio
async def test_inspect_position_by_id_shows_deep_read_only_snapshot(configured_daemon):
    state = TradeStateManager(db_path=str(configured_daemon))
    try:
        spread_id = state.open_position(
            "BTC|ETH",
            "BTC",
            "ETH",
            "LONG_SPREAD",
            100.0,
            50.0,
            0.5,
            0.5,
            -2.0,
            14,
        )
        state.record_tick_signal(
            pair_label="BTC|ETH",
            z_score=-0.5,
            weight_a=0.5,
            weight_b=0.5,
            signal="LONG_SPREAD",
            action="HOLD",
            price_a=110.0,
            price_b=51.0,
        )
    finally:
        state.close()

    update = FakeUpdate(chat_id="123")
    await daemon.bot_inspect(update, _context(args=[str(spread_id)]))

    update.message.reply_text.assert_awaited_once()
    message = update.message.reply_text.await_args.args[0]
    assert "POSITION INSPECTOR #1" in message
    assert "Pair: <b>BTC|ETH</b>" in message
    assert "Entry Z: -2.00" in message
    assert "Z-Score: -0.50" in message
    assert "Signal: LONG_SPREAD" in message
    assert "Action: HOLD" in message
    assert "Unrealized: +4.00%" in message
    assert "OPEN: TARGET_RECORDED x2" in message
    assert "Exchange/client IDs present: NO" in message


@pytest.mark.asyncio
async def test_inspect_position_by_pair_handles_missing_latest_signal(configured_daemon):
    state = TradeStateManager(db_path=str(configured_daemon))
    try:
        state.open_position(
            "BTC|ETH",
            "BTC",
            "ETH",
            "LONG_SPREAD",
            100.0,
            50.0,
            0.5,
            0.5,
            -2.0,
            14,
        )
    finally:
        state.close()

    update = FakeUpdate(chat_id="123")
    await daemon.bot_inspect(update, _context(args=["BTC|ETH"]))

    message = update.message.reply_text.await_args.args[0]
    assert "POSITION INSPECTOR #1" in message
    assert "Z-Score: N/A" in message
    assert "Signal: N/A" in message
    assert "Unrealized: N/A" in message


@pytest.mark.asyncio
async def test_inspect_position_reports_missing_identifier(configured_daemon):
    update = FakeUpdate(chat_id="123")

    await daemon.bot_inspect(update, _context(args=["999"]))

    message = update.message.reply_text.await_args.args[0]
    assert "No open position found" in message
    assert "999" in message


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
    message = update.message.reply_text.await_args.args[0]
    assert "LOCAL STATE STOP ALL" in message
    assert "market" not in message.lower()


@pytest.mark.asyncio
async def test_stop_pair_writes_local_state_command_to_configured_database(configured_daemon):
    update = FakeUpdate(chat_id="123")

    await daemon.bot_stop_pair(update, _context(args=["BTC|ETH"]))

    state = TradeStateManager(db_path=str(configured_daemon))
    try:
        commands = state.get_commands()
    finally:
        state.close()

    assert len(commands) == 1
    assert commands[0]["command"] == "/stop"
    assert commands[0]["target_pair"] == "BTC|ETH"
    message = update.message.reply_text.await_args.args[0]
    assert "LOCAL STATE STOP BTC|ETH" in message


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
