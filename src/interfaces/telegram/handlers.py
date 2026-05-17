"""Telegram command and callback handlers for the operator daemon."""

import html
from io import BytesIO
import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.core.config import settings
from src.engine.trader.reporting.position_inspector import inspect_open_position
from src.engine.trader.runtime.health import (
    build_trader_health_snapshot,
    render_trader_health_snapshot,
)
from src.engine.trader.runtime.pairs import validate_pair_artifact_file
from src.interfaces.telegram import context as telegram_context
from src.interfaces.telegram.renderers import (
    build_position_action_keyboard,
    build_position_select_keyboard,
    format_duration,
    holding_duration_minutes,
    pair_label,
    render_position_action_menu,
    render_position_inspection,
    render_promoted_pairs,
)
from src.interfaces.telegram.plots import (
    PlotDependencyError,
    PlotError,
    build_position_plot_keyboard,
    build_position_zscore_plot,
    render_position_plot_caption,
    render_position_zscore_plot_png,
)


def require_auth(func):
    """Decorator to instantly reject strangers securely."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if str(update.effective_chat.id) != settings.telegram_chat_id:
            logging.warning(f"Unauthorized access attempt from {update.effective_chat.id}")
            return
        return await func(update, context)
    return wrapper


@require_auth
async def bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/status - Replies with the current open positional state of the bot."""
    state = telegram_context.open_state_manager()
    try:
        open_pos = state.get_open_positions()
        equity = state.get_equity_curve()

        eq_str = "No history yet."
        if equity:
            last = equity[-1]
            rpnl = last["realized_pnl_pct"] * 100
            upnl = last["unrealized_pnl_pct"] * 100
            eq_str = f"Realized: {rpnl:.2f}%\nUnrealized: {upnl:.2f}%"
    finally:
        state.close()

    msg = (
        f"📊 <b>TRADER STATUS</b>\n"
        f"Mode: {telegram_context.environment_label()}\n\n"
        f"<b>Portfolio:</b>\n{eq_str}\n\n"
        f"<b>Open Spreads:</b> {len(open_pos)}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


@require_auth
async def bot_positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/positions - Lists all open pairs clearly."""
    state = telegram_context.open_state_manager()
    try:
        open_pos = state.get_open_positions()
    finally:
        state.close()

    if not open_pos:
        await update.message.reply_text("📭 No open positions at the moment.")
        return

    msg = "📂 <b>OPEN POSITIONS</b>\n\n"
    holding_bar_minutes = telegram_context.holding_period_bar_minutes()
    for p in open_pos:
        duration = format_duration(holding_duration_minutes(p, holding_bar_minutes))
        msg += f"• <b>#{p['id']} {p['pair_label']}</b> ({p['side']})\n"
        msg += f"  Duration: {duration}\n"

    await update.message.reply_text(
        msg,
        parse_mode="HTML",
        reply_markup=build_position_select_keyboard(open_pos),
    )


@require_auth
async def bot_promoted_pairs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/pairs - Lists the currently promoted pair artifact."""
    try:
        path = telegram_context.promoted_pairs_path()
        latest_signals = _latest_promoted_pair_signals(path)
        message = render_promoted_pairs(
            path,
            telegram_context.environment_label(),
            latest_signals_by_pair=latest_signals,
        )
    except FileNotFoundError:
        path = telegram_context.promoted_pairs_path()
        message = (
            "📭 <b>PROMOTED PAIRS</b>\n"
            f"No promoted pair artifact found at <code>{html.escape(str(path))}</code>."
        )
    except ValueError as exc:
        message = (
            "⚠️ <b>PROMOTED PAIRS ARTIFACT INVALID</b>\n"
            f"<code>{html.escape(str(exc))}</code>"
        )

    await update.message.reply_text(message, parse_mode="HTML")


def _latest_promoted_pair_signals(path) -> dict[str, dict]:
    artifact = validate_pair_artifact_file(path)
    state = telegram_context.open_state_manager()
    try:
        latest_signals = {}
        for pair in artifact.pairs:
            label = pair_label(pair)
            signals = state.get_tick_signals(label)
            if signals:
                latest_signals[label] = signals[-1]
        return latest_signals
    finally:
        state.close()


@require_auth
async def bot_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/health - Show persisted trader runtime health."""
    state = telegram_context.open_state_manager()
    try:
        snapshot = build_trader_health_snapshot(
            state,
            environment=telegram_context.environment_label() or "N/A",
            stale_after_minutes=telegram_context.health_stale_after_minutes(),
        )
    finally:
        state.close()

    await update.message.reply_text(
        render_trader_health_snapshot(snapshot),
        parse_mode="HTML",
    )


@require_auth
async def bot_inspect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/inspect <ID|PAIR> - Shows detailed read-only state for one open position."""
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /inspect 1 or /inspect BTC/USDT|ETH/USDT")
        return

    identifier = " ".join(context.args).strip()
    state = telegram_context.open_state_manager()
    try:
        inspection = inspect_open_position(state, identifier)
    finally:
        state.close()

    if inspection is None:
        await update.message.reply_text(
            f"📭 No open position found for <code>{html.escape(identifier)}</code>.",
            parse_mode="HTML",
        )
        return

    await update.message.reply_text(
        render_position_inspection(
            inspection,
            telegram_context.holding_period_bar_minutes(),
        ),
        parse_mode="HTML",
    )


@require_auth
async def bot_position_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline button callback for choosing summary or plot for a position."""
    query = update.callback_query
    await query.answer()
    _, position_id = query.data.split(":", 1)

    state = telegram_context.open_state_manager()
    try:
        position = next(
            (
                item for item in state.get_open_positions()
                if str(item["id"]) == position_id
            ),
            None,
        )
    finally:
        state.close()

    if position is None:
        await query.message.reply_text(
            f"📭 No open position found for <code>{html.escape(position_id)}</code>.",
            parse_mode="HTML",
        )
        return

    await query.message.reply_text(
        render_position_action_menu(position),
        parse_mode="HTML",
        reply_markup=build_position_action_keyboard(position_id),
    )


@require_auth
async def bot_inspect_position_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline button callback for one-tap position inspection."""
    query = update.callback_query
    await query.answer()
    _, position_id = query.data.split(":", 1)

    state = telegram_context.open_state_manager()
    try:
        inspection = inspect_open_position(state, position_id)
    finally:
        state.close()

    if inspection is None:
        await query.message.reply_text(
            f"📭 No open position found for <code>{html.escape(position_id)}</code>.",
            parse_mode="HTML",
        )
        return

    await query.message.reply_text(
        render_position_inspection(
            inspection,
            telegram_context.holding_period_bar_minutes(),
        ),
        parse_mode="HTML",
    )


@require_auth
async def bot_plot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/plot <ID|PAIR> - Sends a read-only z-score/PnL chart."""
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /plot 7")
        return

    identifier = " ".join(context.args).strip()
    state = telegram_context.open_state_manager()
    try:
        try:
            plot = build_position_zscore_plot(state, identifier)
            png = render_position_zscore_plot_png(plot)
        except PlotDependencyError as exc:
            await update.message.reply_text(f"⚠️ {html.escape(str(exc))}")
            return
        except PlotError as exc:
            await update.message.reply_text(
                f"📭 {html.escape(str(exc))}",
                parse_mode="HTML",
            )
            return
    finally:
        state.close()

    photo = BytesIO(png)
    photo.name = f"position_{plot.position['id']}_zscore.png"
    await update.message.reply_photo(
        photo=photo,
        caption=render_position_plot_caption(plot),
        parse_mode="HTML",
        reply_markup=build_position_plot_keyboard(plot.position["id"]),
    )


@require_auth
async def bot_plot_position_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline button callback for refreshing one position plot."""
    query = update.callback_query
    await query.answer()
    _, position_id = query.data.split(":", 1)

    state = telegram_context.open_state_manager()
    try:
        try:
            plot = build_position_zscore_plot(state, position_id)
            png = render_position_zscore_plot_png(plot)
        except PlotDependencyError as exc:
            await query.message.reply_text(f"⚠️ {html.escape(str(exc))}")
            return
        except PlotError as exc:
            await query.message.reply_text(
                f"📭 {html.escape(str(exc))}",
                parse_mode="HTML",
            )
            return
    finally:
        state.close()

    photo = BytesIO(png)
    photo.name = f"position_{plot.position['id']}_zscore.png"
    await query.message.reply_photo(
        photo=photo,
        caption=render_position_plot_caption(plot),
        parse_mode="HTML",
        reply_markup=build_position_plot_keyboard(plot.position["id"]),
    )


@require_auth
async def bot_stop_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stop_all - Instructs the Trader to immediately liquidate."""
    state = telegram_context.open_state_manager()
    try:
        state.write_command("/stop_all")
    finally:
        state.close()

    await update.message.reply_text(
        "🚨 <b>COMMAND LOGGED: LOCAL STATE STOP ALL</b>\n"
        "The executing trader will record forced local closes on its next command sweep.",
        parse_mode="HTML",
    )


@require_auth
async def bot_stop_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stop <PAIR> - Instructs immediate liquidation for one pair."""
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /stop BTC/USDT")
        return

    target = context.args[0].upper()
    state = telegram_context.open_state_manager()
    try:
        state.write_command("/stop", target_pair=target)
    finally:
        state.close()

    await update.message.reply_text(
        f"🚨 <b>COMMAND LOGGED: LOCAL STATE STOP {target}</b>\n"
        "The executing trader will record a forced local close on its next command sweep.",
        parse_mode="HTML",
    )


@require_auth
async def bot_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/pause - Tells Trader to skip future entries."""
    state = telegram_context.open_state_manager()
    try:
        state.write_command("/pause")
    finally:
        state.close()
    await update.message.reply_text("⏳ <b>COMMAND LOGGED: PAUSE</b>", parse_mode="HTML")


@require_auth
async def bot_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/resume - Tells Trader to resume normal tick execution."""
    state = telegram_context.open_state_manager()
    try:
        state.write_command("/resume")
    finally:
        state.close()
    await update.message.reply_text("▶️ <b>COMMAND LOGGED: RESUME</b>", parse_mode="HTML")


@require_auth
async def bot_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/help - Command list."""
    msg = (
        "🤖 <b>Stat-Arb Controller</b>\n\n"
        "/status - System PNL & Open Count\n"
        "/health - Runtime health and staleness\n"
        "/positions - Detailed layout of active pairs\n"
        "/pairs - Currently promoted research pairs\n"
        "/inspect [ID|PAIR] - Deep read-only position view\n"
        "/plot [ID|PAIR] - Z-score and PnL chart\n"
        "/pause - Skip new trades (Holds existing)\n"
        "/resume - Revert pause mechanism\n"
        "/stop [PAIR] - Requests one forced local-state close\n"
        "/stop_all - Requests forced local-state close for everything"
    )
    await update.message.reply_text(msg, parse_mode="HTML")
