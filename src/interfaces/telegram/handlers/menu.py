"""Telegram operator menu handlers."""

from telegram import Update
from telegram.ext import ContextTypes

from src.interfaces.telegram import context as telegram_context
from src.interfaces.telegram.handlers.auth import require_auth
from src.interfaces.telegram.handlers.controls import (
    _write_pause,
    _write_resume,
    _write_stop_all,
)
from src.interfaces.telegram.handlers.pairs import _reply_promoted_pairs
from src.interfaces.telegram.handlers.positions import _reply_positions
from src.interfaces.telegram.handlers.runtime import (
    _reply_health,
    _reply_run_status,
    _reply_status,
)
from src.interfaces.telegram.renderers import (
    build_menu_section_keyboard,
    build_operator_menu_keyboard,
    build_stop_all_confirmation_keyboard,
    render_menu_section,
    render_operator_menu,
)


@require_auth
async def bot_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/menu - Show the top-level operator command tree."""
    await update.message.reply_text(
        render_operator_menu(telegram_context.environment_label()),
        parse_mode="HTML",
        reply_markup=build_operator_menu_keyboard(),
    )


@require_auth
async def bot_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inline callback handler for the operator menu tree."""
    query = update.callback_query
    await query.answer()
    _, action = query.data.split(":", 1)

    if action == "main":
        await query.message.reply_text(
            render_operator_menu(telegram_context.environment_label()),
            parse_mode="HTML",
            reply_markup=build_operator_menu_keyboard(),
        )
        return
    if action in {"runtime", "positions", "pairs", "reports", "controls"}:
        await query.message.reply_text(
            render_menu_section(action),
            parse_mode="HTML",
            reply_markup=build_menu_section_keyboard(action),
        )
        return
    if action == "status":
        await _reply_status(query.message)
        return
    if action == "health":
        await _reply_health(query.message)
        return
    if action == "run_status":
        await _reply_run_status(query.message)
        return
    if action == "positions_open":
        await _reply_positions(query.message)
        return
    if action == "promoted_pairs":
        await _reply_promoted_pairs(query.message)
        return
    if action == "pause":
        await _write_pause(query.message)
        return
    if action == "resume":
        await _write_resume(query.message)
        return
    if action == "stop_all_confirm":
        await query.message.reply_text(
            "🚨 <b>CONFIRM LOCAL STATE STOP ALL</b>\n"
            "This records a stop-all command for the execution flow.",
            parse_mode="HTML",
            reply_markup=build_stop_all_confirmation_keyboard(),
        )
        return
    if action == "stop_all_execute":
        await _write_stop_all(query.message)
        return

    await query.message.reply_text("⚠️ Unknown menu action.")


@require_auth
async def bot_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help - Command list."""
    msg = (
        "🤖 <b>Stat-Arb Controller</b>\n\n"
        "/menu - Button-based operator menu\n"
        "/status - System PNL & Open Count\n"
        "/health - Runtime health and staleness\n"
        "/run_status or /drill - Local run lifecycle\n"
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
