"""Telegram operator control handlers."""

from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from src.interfaces.telegram import context as telegram_context
from src.interfaces.telegram.handlers.auth import require_auth


@require_auth
async def bot_stop_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/stop_all - Instructs the Trader to immediately liquidate."""
    await _write_stop_all(update.message)


async def _write_stop_all(reply_target: Any) -> None:
    state = telegram_context.open_state_manager()
    try:
        state.write_command("/stop_all")
    finally:
        state.close()

    await reply_target.reply_text(
        "🚨 <b>COMMAND LOGGED: LOCAL STATE STOP ALL</b>\n"
        "The executing trader will record forced local closes on its next command sweep.",
        parse_mode="HTML",
    )


@require_auth
async def bot_stop_pair(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
async def bot_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/pause - Tells Trader to skip future entries."""
    await _write_pause(update.message)


async def _write_pause(reply_target: Any) -> None:
    state = telegram_context.open_state_manager()
    try:
        state.write_command("/pause")
    finally:
        state.close()
    await reply_target.reply_text("⏳ <b>COMMAND LOGGED: PAUSE</b>", parse_mode="HTML")


@require_auth
async def bot_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/resume - Tells Trader to resume normal tick execution."""
    await _write_resume(update.message)


async def _write_resume(reply_target: Any) -> None:
    state = telegram_context.open_state_manager()
    try:
        state.write_command("/resume")
    finally:
        state.close()
    await reply_target.reply_text("▶️ <b>COMMAND LOGGED: RESUME</b>", parse_mode="HTML")
