import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.config import settings
from src.engine.trader.runtime.pairs import build_pair_artifact
from src.engine.trader.runtime.run_status import record_observer_max_ticks_completed
from src.engine.trader.state_manager import TradeStateManager
from src.interfaces.telegram import daemon
from src.interfaces.telegram import context as telegram_context
from src.interfaces.telegram import plots
from src.interfaces.telegram import renderers


class FakeUpdate:
    def __init__(self, chat_id: str):
        self.effective_chat = SimpleNamespace(id=chat_id)
        self.message = SimpleNamespace(
            reply_text=AsyncMock(),
            reply_photo=AsyncMock(),
        )


class FakeCallbackUpdate:
    def __init__(self, chat_id: str, callback_data: str):
        self.effective_chat = SimpleNamespace(id=chat_id)
        self.callback_query = SimpleNamespace(
            data=callback_data,
            answer=AsyncMock(),
            message=SimpleNamespace(
                reply_text=AsyncMock(),
                reply_photo=AsyncMock(),
            ),
        )


@pytest.fixture
def configured_daemon(tmp_path):
    db_path = tmp_path / "trader.db"
    pairs_path = tmp_path / "surviving_pairs.json"
    cfg_path = tmp_path / "telegram.yml"
    cfg_path.write_text(
        "telegram:\n"
        "  environment: TEST\n"
        "  bot_name: '@TestBot'\n"
        f"  db_path: '{db_path}'\n"
        "  holding_period_bar_minutes: 1\n"
        f"  promoted_pairs_path: '{pairs_path}'\n"
        "  health_stale_after_minutes: 5\n"
    )

    settings.telegram_chat_id = "123"
    cfg = daemon.configure_daemon(str(cfg_path))
    assert cfg.environment == "TEST"
    assert cfg.db_path == str(db_path)
    yield db_path
    telegram_context.reset_daemon_context()


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
    reply_kwargs = update.message.reply_text.await_args.kwargs
    keyboard = reply_kwargs["reply_markup"].inline_keyboard
    message = update.message.reply_text.await_args.args[0]
    assert "OPEN POSITIONS" in message
    assert "#1 BTC|ETH" in message
    assert "BTC|ETH" in message
    assert "Duration:" in message
    assert keyboard[0][0].text == "Position #1"
    assert keyboard[0][0].callback_data == "position_menu:1"
    assert renderers.holding_duration_minutes({"holding_bars": 6}, 1) == 6
    assert renderers.format_duration(6) == "6m"
    assert renderers.format_duration(240) == "4h"


@pytest.mark.asyncio
async def test_position_menu_button_offers_summary_or_plot(configured_daemon):
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
    finally:
        state.close()

    update = FakeCallbackUpdate(
        chat_id="123",
        callback_data=f"position_menu:{spread_id}",
    )
    await daemon.bot_position_menu_callback(update, _context())

    update.callback_query.answer.assert_awaited_once()
    update.callback_query.message.reply_text.assert_awaited_once()
    message = update.callback_query.message.reply_text.await_args.args[0]
    keyboard = update.callback_query.message.reply_text.await_args.kwargs[
        "reply_markup"
    ].inline_keyboard
    assert "POSITION #1" in message
    assert "BTC|ETH" in message
    assert keyboard[0][0].text == "Summary"
    assert keyboard[0][0].callback_data == "inspect_position:1"
    assert keyboard[0][1].text == "Plot"
    assert keyboard[0][1].callback_data == "plot_position:1"


@pytest.mark.asyncio
async def test_position_inspect_button_renders_snapshot(configured_daemon):
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
    finally:
        state.close()

    update = FakeCallbackUpdate(
        chat_id="123",
        callback_data=f"inspect_position:{spread_id}",
    )
    await daemon.bot_inspect_position_callback(update, _context())

    update.callback_query.answer.assert_awaited_once()
    update.callback_query.message.reply_text.assert_awaited_once()
    message = update.callback_query.message.reply_text.await_args.args[0]
    assert "POSITION INSPECTOR #1" in message
    assert "Pair: <b>BTC|ETH</b>" in message


@pytest.mark.asyncio
async def test_position_inspect_button_reports_stale_position(configured_daemon):
    update = FakeCallbackUpdate(chat_id="123", callback_data="inspect_position:999")

    await daemon.bot_inspect_position_callback(update, _context())

    update.callback_query.answer.assert_awaited_once()
    message = update.callback_query.message.reply_text.await_args.args[0]
    assert "No open position found" in message
    assert "999" in message


@pytest.mark.asyncio
async def test_promoted_pairs_lists_configured_artifact(configured_daemon):
    pairs_path = configured_daemon.parent / "surviving_pairs.json"
    pairs_path.write_text(
        json.dumps(
            build_pair_artifact(
                pair_rows=[
                    {
                        "Asset_X": "BTC/USDT",
                        "Asset_Y": "ETH/USDT",
                        "Hedge_Ratio": 1.2,
                        "Half_Life": 42.0,
                        "P_Value": 0.03,
                        "Best_Params": {"lookback_bars": 120, "entry_z": 2.0},
                        "Performance": {
                            "final_pnl_pct": 1.25,
                            "sharpe_ratio": 3.5,
                        },
                    }
                ],
                timeframe="1m",
                exchange="bybit",
                generated_at="2026-05-16T23:50:56+00:00",
            )
        ),
        encoding="utf-8",
    )
    state = TradeStateManager(db_path=str(configured_daemon))
    try:
        state.record_tick_signal(
            pair_label="BTC/USDT|ETH/USDT",
            z_score=-1.75,
            weight_a=0.5,
            weight_b=0.5,
            signal="FLAT",
            action="SKIP",
            price_a=100.0,
            price_b=50.0,
        )
    finally:
        state.close()

    update = FakeUpdate(chat_id="123")
    await daemon.bot_promoted_pairs(update, _context())

    update.message.reply_text.assert_awaited_once()
    message = update.message.reply_text.await_args.args[0]
    assert "PROMOTED PAIRS" in message
    assert "Mode: TEST" in message
    assert "bybit 1m | Count: 1" in message
    assert "BTC/USDT|ETH/USDT" in message
    assert "Sharpe: 3.50" in message
    assert "PnL: +1.25%" in message
    assert "Entry Z: 2.00" in message
    assert "Lookback: 120 bars" in message
    assert "Latest Z: -1.75" in message
    assert "Entry Gap: 0.25" in message
    assert "Action: SKIP" in message


@pytest.mark.asyncio
async def test_promoted_pairs_reports_missing_artifact(configured_daemon):
    update = FakeUpdate(chat_id="123")

    await daemon.bot_promoted_pairs(update, _context())

    message = update.message.reply_text.await_args.args[0]
    assert "PROMOTED PAIRS" in message
    assert "No promoted pair artifact found" in message


@pytest.mark.asyncio
async def test_health_reports_runtime_state(configured_daemon):
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
        state.record_tick_signal(
            pair_label="BTC|ETH",
            z_score=-1.0,
            weight_a=0.5,
            weight_b=0.5,
            signal="LONG_SPREAD",
            action="HOLD",
            price_a=101.0,
            price_b=49.0,
        )
        state.snapshot_equity(
            total_equity_pct=0.03,
            open_positions=1,
            realized_pnl_pct=0.01,
            unrealized_pnl_pct=0.02,
        )
    finally:
        state.close()

    update = FakeUpdate(chat_id="123")
    await daemon.bot_health(update, _context())

    update.message.reply_text.assert_awaited_once()
    message = update.message.reply_text.await_args.args[0]
    assert "TRADER HEALTH" in message
    assert "Mode: TEST" in message
    assert "Open Positions: 1" in message
    assert "Equity: +3.0000%" in message
    assert "Realized: +1.0000%" in message
    assert "Unrealized: +2.0000%" in message


@pytest.mark.asyncio
async def test_menu_shows_operator_tree(configured_daemon):
    update = FakeUpdate(chat_id="123")

    await daemon.bot_menu(update, _context())

    update.message.reply_text.assert_awaited_once()
    message = update.message.reply_text.await_args.args[0]
    keyboard = update.message.reply_text.await_args.kwargs["reply_markup"].inline_keyboard
    assert "STAT-ARB CONTROLLER" in message
    assert "Mode: TEST" in message
    assert keyboard[0][0].text == "Runtime"
    assert keyboard[0][0].callback_data == "menu:runtime"
    assert keyboard[1][0].text == "Pairs"


@pytest.mark.asyncio
async def test_menu_runtime_section_offers_run_status(configured_daemon):
    update = FakeCallbackUpdate(chat_id="123", callback_data="menu:runtime")

    await daemon.bot_menu_callback(update, _context())

    update.callback_query.answer.assert_awaited_once()
    message = update.callback_query.message.reply_text.await_args.args[0]
    keyboard = update.callback_query.message.reply_text.await_args.kwargs[
        "reply_markup"
    ].inline_keyboard
    assert "RUNTIME" in message
    assert keyboard[1][0].text == "Run Status"
    assert keyboard[1][0].callback_data == "menu:run_status"


@pytest.mark.asyncio
async def test_run_status_reports_max_tick_completion_and_state_only_safety(
    configured_daemon,
):
    pairs_path = configured_daemon.parent / "surviving_pairs.json"
    pairs_path.write_text(
        json.dumps(
            build_pair_artifact(
                pair_rows=[
                    {
                        "Asset_X": "BTC/USDT",
                        "Asset_Y": "ETH/USDT",
                        "Hedge_Ratio": 1.2,
                        "Half_Life": 42.0,
                        "P_Value": 0.03,
                        "Best_Params": {"lookback_bars": 120, "entry_z": 2.0},
                        "Performance": {
                            "final_pnl_pct": 1.25,
                            "sharpe_ratio": 3.5,
                        },
                    }
                ],
                timeframe="1m",
                exchange="bybit",
                generated_at="2026-05-16T23:50:56+00:00",
            )
        ),
        encoding="utf-8",
    )
    state = TradeStateManager(db_path=str(configured_daemon))
    try:
        spread_id = state.open_position(
            "BTC/USDT|ETH/USDT",
            "BTC/USDT",
            "ETH/USDT",
            "LONG_SPREAD",
            100.0,
            50.0,
            0.5,
            0.5,
            -2.0,
            120,
        )
        state.record_tick_signal(
            pair_label="BTC/USDT|ETH/USDT",
            z_score=-1.0,
            weight_a=0.5,
            weight_b=0.5,
            signal="LONG_SPREAD",
            action="HOLD",
            price_a=101.0,
            price_b=49.0,
        )
        record_observer_max_ticks_completed(
            state,
            max_ticks=180,
            completed_ticks=180,
            open_position_ids=[spread_id],
        )
    finally:
        state.close()

    update = FakeUpdate(chat_id="123")
    await daemon.bot_run_status(update, _context())

    update.message.reply_text.assert_awaited_once()
    message = update.message.reply_text.await_args.args[0]
    assert "RUN STATUS" in message
    assert "CLEANLY_STOPPED_MAX_TICKS" in message
    assert "Completed 180 ticks" in message
    assert "Open IDs: #1" in message
    assert "State-only order-id invariant: PASS" in message
    assert "Report JSON parse: OK" in message


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


def test_position_zscore_plot_filters_signals_and_renders_png(configured_daemon):
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
            z_score=-2.0,
            weight_a=0.5,
            weight_b=0.5,
            signal="LONG_SPREAD",
            action="ENTRY",
            price_a=100.0,
            price_b=50.0,
        )
        state.record_tick_signal(
            pair_label="BTC|ETH",
            z_score=-1.2,
            weight_a=0.5,
            weight_b=0.5,
            signal="LONG_SPREAD",
            action="HOLD",
            price_a=104.0,
            price_b=49.0,
        )

        plot = plots.build_position_zscore_plot(state, str(spread_id))
        png = plots.render_position_zscore_plot_png(plot)
    finally:
        state.close()

    assert len(plot.signals) == 2
    assert plot.latest_signal["z_score"] == -1.2
    assert plot.pnl_values[-1] == pytest.approx(0.03)
    assert png.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_plot_command_sends_zscore_png(configured_daemon):
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
            z_score=-1.0,
            weight_a=0.5,
            weight_b=0.5,
            signal="LONG_SPREAD",
            action="HOLD",
            price_a=101.0,
            price_b=49.0,
        )
    finally:
        state.close()

    update = FakeUpdate(chat_id="123")
    await daemon.bot_plot(update, _context(args=[str(spread_id)]))

    update.message.reply_photo.assert_awaited_once()
    kwargs = update.message.reply_photo.await_args.kwargs
    assert kwargs["photo"].getvalue().startswith(b"\x89PNG")
    assert "Z-SCORE PLOT #1" in kwargs["caption"]
    assert "Latest Z: -1.00" in kwargs["caption"]
    keyboard = kwargs["reply_markup"].inline_keyboard
    assert keyboard[0][0].text == "Refresh Plot #1"
    assert keyboard[0][0].callback_data == "plot_position:1"


@pytest.mark.asyncio
async def test_plot_refresh_button_sends_updated_png(configured_daemon):
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
            z_score=-0.8,
            weight_a=0.5,
            weight_b=0.5,
            signal="LONG_SPREAD",
            action="HOLD",
            price_a=102.0,
            price_b=49.5,
        )
    finally:
        state.close()

    update = FakeCallbackUpdate(
        chat_id="123",
        callback_data=f"plot_position:{spread_id}",
    )
    await daemon.bot_plot_position_callback(update, _context())

    update.callback_query.answer.assert_awaited_once()
    update.callback_query.message.reply_photo.assert_awaited_once()
    kwargs = update.callback_query.message.reply_photo.await_args.kwargs
    assert kwargs["photo"].getvalue().startswith(b"\x89PNG")
    assert "Latest Z: -0.80" in kwargs["caption"]


@pytest.mark.asyncio
async def test_plot_reports_missing_position(configured_daemon):
    update = FakeUpdate(chat_id="123")

    await daemon.bot_plot(update, _context(args=["999"]))

    update.message.reply_photo.assert_not_awaited()
    message = update.message.reply_text.await_args.args[0]
    assert "No position found" in message
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
