"""Telegram promoted-pair handlers."""

import html
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from src.engine.trader.runtime.artifacts import validate_pair_artifact_file
from src.interfaces.telegram import context as telegram_context
from src.interfaces.telegram.handlers.auth import require_auth
from src.interfaces.telegram.rendering.pairs import (
    pair_label,
    render_promoted_pairs,
)


@require_auth
async def bot_promoted_pairs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/pairs - Lists the currently promoted pair artifact."""
    await _reply_promoted_pairs(update.message)


async def _reply_promoted_pairs(reply_target: Any) -> None:
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

    await reply_target.reply_text(message, parse_mode="HTML")


def _latest_promoted_pair_signals(path: Path) -> dict[str, dict]:
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
