"""Telegram position and plot handlers."""

import html
from io import BytesIO
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from src.engine.trader.reporting.position_inspector import inspect_open_position
from src.interfaces.telegram import context as telegram_context
from src.interfaces.telegram.handlers.auth import require_auth
from src.interfaces.telegram.plots import (
    PlotDependencyError,
    PlotError,
    build_position_plot_keyboard,
    build_position_zscore_plot,
    render_position_plot_caption,
    render_position_zscore_plot_png,
)
from src.interfaces.telegram.renderers import (
    build_position_action_keyboard,
    build_position_select_keyboard,
    format_duration,
    holding_duration_minutes,
    render_position_action_menu,
    render_position_inspection,
)


@require_auth
async def bot_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/positions - Lists all open pairs clearly."""
    await _reply_positions(update.message)


async def _reply_positions(reply_target: Any) -> None:
    state = telegram_context.open_state_manager()
    try:
        open_pos = state.get_open_positions()
    finally:
        state.close()

    if not open_pos:
        await reply_target.reply_text("📭 No open positions at the moment.")
        return

    msg = "📂 <b>OPEN POSITIONS</b>\n\n"
    holding_bar_minutes = telegram_context.holding_period_bar_minutes()
    for position in open_pos:
        duration = format_duration(
            holding_duration_minutes(position, holding_bar_minutes)
        )
        msg += (
            f"• <b>#{position['id']} {position['pair_label']}</b> "
            f"({position['side']})\n"
        )
        msg += f"  Duration: {duration}\n"

    await reply_target.reply_text(
        msg,
        parse_mode="HTML",
        reply_markup=build_position_select_keyboard(open_pos),
    )


@require_auth
async def bot_inspect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
async def bot_position_menu_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
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
async def bot_inspect_position_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
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
async def bot_plot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
async def bot_plot_position_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
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
