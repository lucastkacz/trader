"""Authentication guard for Telegram command handlers."""

import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from src.core.config import settings


def require_auth(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Decorator to instantly reject strangers securely."""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if str(update.effective_chat.id) != settings.telegram_chat_id:
            logging.warning("Unauthorized access attempt from %s", update.effective_chat.id)
            return None
        return await func(update, context)

    return wrapper
