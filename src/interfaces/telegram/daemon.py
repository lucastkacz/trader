"""
Telegram Interactive UI Daemon
==============================
Runs infinitely via python-telegram-bot to listen for commands.
Reads from and writes strictly to the SQLite database.
Never touches trading exchanges or networking modules directly.
"""

import sys
import argparse
import logging
from typing import Any, Dict, Optional

import yaml
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from src.core.config import settings
from src.engine.trader.state_manager import TradeStateManager

# Minimal basic logging for the listener itself
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_DB_PATH: Optional[str] = None
TELEGRAM_ENVIRONMENT = "UNKNOWN"


def load_telegram_config(config_path: str) -> Dict[str, Any]:
    """Load the telegram YAML block from a config file."""
    with open(config_path, "r") as f:
        data = yaml.safe_load(f) or {}

    cfg = data.get("telegram", data)
    if not cfg.get("db_path"):
        raise ValueError(f"Telegram config missing required db_path: {config_path}")
    return cfg


def configure_daemon(config_path: str) -> Dict[str, Any]:
    """Configure daemon process globals from YAML."""
    global TELEGRAM_DB_PATH, TELEGRAM_ENVIRONMENT
    cfg = load_telegram_config(config_path)
    TELEGRAM_DB_PATH = cfg["db_path"]
    TELEGRAM_ENVIRONMENT = cfg.get("environment", "UNKNOWN")
    return cfg


def open_state_manager() -> TradeStateManager:
    """Open a short-lived state connection for one command handler."""
    if TELEGRAM_DB_PATH is None:
        raise RuntimeError("Telegram daemon db_path is not configured")
    return TradeStateManager(db_path=TELEGRAM_DB_PATH)


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
    state = open_state_manager()
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
        f"Mode: {TELEGRAM_ENVIRONMENT}\n\n"
        f"<b>Portfolio:</b>\n{eq_str}\n\n"
        f"<b>Open Spreads:</b> {len(open_pos)}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

@require_auth
async def bot_positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/positions - Lists all open pairs clearly."""
    state = open_state_manager()
    try:
        open_pos = state.get_open_positions()
    finally:
        state.close()

    if not open_pos:
        await update.message.reply_text("📭 No open positions at the moment.")
        return

    msg = "📂 <b>OPEN POSITIONS</b>\n\n"
    for p in open_pos:
        duration = p.get('holding_bars', 0) * 4
        msg += f"• <b>{p['pair_label']}</b> ({p['side']})\n"
        msg += f"  Duration: {duration}h\n"
        
    await update.message.reply_text(msg, parse_mode="HTML")

@require_auth
async def bot_stop_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stop_all - Instructs the Trader to immediately liquidate."""
    state = open_state_manager()
    try:
        state.write_command("/stop_all")
    finally:
        state.close()
    
    await update.message.reply_text(
        "🚨 <b>COMMAND LOGGED: STOP ALL</b>\n"
        "The executing daemon will detect this within 10 seconds and liquidate strictly at market.",
        parse_mode="HTML"
    )

@require_auth
async def bot_stop_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stop <PAIR> - Instructs immediate liquidation for one pair."""
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /stop BTC/USDT")
        return
        
    target = context.args[0].upper()
    state = open_state_manager()
    try:
        state.write_command("/stop", target_pair=target)
    finally:
        state.close()
    
    await update.message.reply_text(
        f"🚨 <b>COMMAND LOGGED: STOP {target}</b>\n"
        f"Awaiting 10-second loop sweep...",
        parse_mode="HTML"
    )

@require_auth
async def bot_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/pause - Tells Trader to skip future entries."""
    state = open_state_manager()
    try:
        state.write_command("/pause")
    finally:
        state.close()
    await update.message.reply_text("⏳ <b>COMMAND LOGGED: PAUSE</b>", parse_mode="HTML")

@require_auth
async def bot_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/resume - Tells Trader to resume normal tick execution."""
    state = open_state_manager()
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
        "/positions - Detailed layout of active pairs\n"
        "/pause - Skip new trades (Holds existing)\n"
        "/resume - Revert pause mechanism\n"
        "/stop [PAIR] - Closes one pair immediately\n"
        "/stop_all - Closes EVERYTHING immediately"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

def build_application():
    """Build the Telegram polling application."""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logging.critical("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing in .env")
        sys.exit(1)

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", bot_help))
    app.add_handler(CommandHandler("help", bot_help))
    app.add_handler(CommandHandler("status", bot_status))
    app.add_handler(CommandHandler("positions", bot_positions))
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

if __name__ == '__main__':
    main()
