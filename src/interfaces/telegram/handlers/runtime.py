"""Telegram runtime status handlers."""

from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from src.engine.trader.runtime.monitoring.health import (
    build_trader_health_snapshot,
    render_trader_health_snapshot,
)
from src.engine.trader.runtime.monitoring.run_status import build_run_status_snapshot
from src.interfaces.telegram import context as telegram_context
from src.interfaces.telegram.handlers.auth import require_auth
from src.interfaces.telegram.rendering.runtime import render_run_status


@require_auth
async def bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/status - Replies with the current open positional state of the bot."""
    await _reply_status(update.message)


async def _reply_status(reply_target: Any) -> None:
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
        "📊 <b>TRADER STATUS</b>\n"
        f"Mode: {telegram_context.environment_label()}\n\n"
        f"<b>Portfolio:</b>\n{eq_str}\n\n"
        f"<b>Open Spreads:</b> {len(open_pos)}"
    )
    await reply_target.reply_text(msg, parse_mode="HTML")


@require_auth
async def bot_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/health - Show persisted trader runtime health."""
    await _reply_health(update.message)


async def _reply_health(reply_target: Any) -> None:
    state = telegram_context.open_state_manager()
    try:
        snapshot = build_trader_health_snapshot(
            state,
            environment=telegram_context.environment_label() or "N/A",
            stale_after_minutes=telegram_context.health_stale_after_minutes(),
        )
    finally:
        state.close()

    await reply_target.reply_text(
        render_trader_health_snapshot(snapshot),
        parse_mode="HTML",
    )


@require_auth
async def bot_run_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/run_status - Show local observer drill lifecycle status."""
    await _reply_run_status(update.message)


async def _reply_run_status(reply_target: Any) -> None:
    state = telegram_context.open_state_manager()
    try:
        snapshot = build_run_status_snapshot(
            state,
            environment=telegram_context.environment_label() or "N/A",
            stale_after_minutes=telegram_context.health_stale_after_minutes(),
            surviving_pairs_path=telegram_context.promoted_pairs_path(),
        )
    finally:
        state.close()

    await reply_target.reply_text(
        render_run_status(snapshot),
        parse_mode="HTML",
    )
