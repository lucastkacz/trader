"""Compatibility facade for Telegram command and callback handlers."""

from src.interfaces.telegram.handlers.auth import require_auth
from src.interfaces.telegram.handlers.controls import (
    bot_pause,
    bot_resume,
    bot_stop_all,
    bot_stop_pair,
)
from src.interfaces.telegram.handlers.menu import (
    bot_help,
    bot_menu,
    bot_menu_callback,
)
from src.interfaces.telegram.handlers.pairs import bot_promoted_pairs
from src.interfaces.telegram.handlers.positions import (
    bot_inspect,
    bot_inspect_position_callback,
    bot_plot,
    bot_plot_position_callback,
    bot_position_menu_callback,
    bot_positions,
)
from src.interfaces.telegram.handlers.runtime import (
    bot_health,
    bot_run_status,
    bot_status,
)

__all__ = [
    "bot_health",
    "bot_help",
    "bot_inspect",
    "bot_inspect_position_callback",
    "bot_menu",
    "bot_menu_callback",
    "bot_pause",
    "bot_plot",
    "bot_plot_position_callback",
    "bot_position_menu_callback",
    "bot_positions",
    "bot_promoted_pairs",
    "bot_resume",
    "bot_run_status",
    "bot_status",
    "bot_stop_all",
    "bot_stop_pair",
    "require_auth",
]
