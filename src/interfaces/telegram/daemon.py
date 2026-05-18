"""
Telegram Interactive UI Daemon
==============================
Runs infinitely via python-telegram-bot to listen for commands.
Reads from and writes strictly to the SQLite database.
Never touches trading exchanges or networking modules directly.
"""

import argparse
import logging
import sys

from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler

from src.core.config import settings
from src.interfaces.telegram.context import configure_daemon
from src.interfaces.telegram.handlers import (
    bot_health,
    bot_help,
    bot_inspect,
    bot_inspect_position_callback,
    bot_menu,
    bot_menu_callback,
    bot_pause,
    bot_position_menu_callback,
    bot_plot,
    bot_plot_position_callback,
    bot_positions,
    bot_promoted_pairs,
    bot_resume,
    bot_run_status,
    bot_status,
    bot_stop_all,
    bot_stop_pair,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def build_application():
    """Build the Telegram polling application."""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logging.critical("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing in .env")
        sys.exit(1)

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", bot_menu))
    app.add_handler(CommandHandler("menu", bot_menu))
    app.add_handler(CommandHandler("help", bot_help))
    app.add_handler(CommandHandler("health", bot_health))
    app.add_handler(CommandHandler("run_status", bot_run_status))
    app.add_handler(CommandHandler("drill", bot_run_status))
    app.add_handler(CommandHandler("status", bot_status))
    app.add_handler(CommandHandler("positions", bot_positions))
    app.add_handler(CommandHandler("pairs", bot_promoted_pairs))
    app.add_handler(CommandHandler("promoted_pairs", bot_promoted_pairs))
    app.add_handler(CommandHandler("inspect", bot_inspect))
    app.add_handler(CommandHandler("plot", bot_plot))
    app.add_handler(
        CallbackQueryHandler(bot_position_menu_callback, pattern="^position_menu:")
    )
    app.add_handler(CallbackQueryHandler(bot_menu_callback, pattern="^menu:"))
    app.add_handler(
        CallbackQueryHandler(bot_inspect_position_callback, pattern="^inspect_position:")
    )
    app.add_handler(
        CallbackQueryHandler(bot_plot_position_callback, pattern="^plot_position:")
    )
    app.add_handler(CommandHandler("stop_all", bot_stop_all))
    app.add_handler(CommandHandler("stop", bot_stop_pair))
    app.add_handler(CommandHandler("pause", bot_pause))
    app.add_handler(CommandHandler("resume", bot_resume))
    return app


def main():
    parser = argparse.ArgumentParser(description="Trader Telegram command daemon")
    parser.add_argument("--config", type=str, required=True, help="Path to telegram YAML config")
    args = parser.parse_args()

    configure_daemon(args.config)
    app = build_application()

    logging.info("Telegram UI Daemon Started. Listening for commands...")
    app.run_polling()


if __name__ == "__main__":
    main()
