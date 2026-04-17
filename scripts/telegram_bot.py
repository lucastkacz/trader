"""
Telegram Interactive UI Daemon
==============================
Runs infinitely via python-telegram-bot to listen for commands.
Reads from and writes strictly to the SQLite database.
Never touches trading exchanges or networking modules directly.
"""

import sys
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from src.core.config import settings
from src.engine.ghost.state_manager import GhostStateManager

# Minimal basic logging for the listener itself
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
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
    state = GhostStateManager()
    open_pos = state.get_open_positions()
    equity = state.get_equity_curve()
    
    eq_str = "No history yet."
    if equity:
        last = equity[-1]
        rpnl = last["realized_pnl_pct"] * 100
        upnl = last["unrealized_pnl_pct"] * 100
        eq_str = f"Realized: {rpnl:.2f}%\nUnrealized: {upnl:.2f}%"

    msg = (
        f"📊 <b>GHOST TRADER STATUS</b>\n"
        f"Mode: {settings.env.upper()}\n\n"
        f"<b>Portfolio:</b>\n{eq_str}\n\n"
        f"<b>Open Spreads:</b> {len(open_pos)}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")
    state.close()

@require_auth
async def bot_positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/positions - Lists all open pairs clearly."""
    state = GhostStateManager()
    open_pos = state.get_open_positions()
    
    if not open_pos:
        await update.message.reply_text("📭 No open positions at the moment.")
        state.close()
        return

    msg = "📂 <b>OPEN POSITIONS</b>\n\n"
    for p in open_pos:
        duration = p.get('holding_bars', 0) * 4
        msg += f"• <b>{p['pair_label']}</b> ({p['side']})\n"
        msg += f"  Duration: {duration}h\n"
        
    await update.message.reply_text(msg, parse_mode="HTML")
    state.close()

@require_auth
async def bot_stop_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stop_all - Instructs the Ghost Trader to immediately liquidate."""
    state = GhostStateManager()
    state.write_command("/stop_all")
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
    state = GhostStateManager()
    state.write_command("/stop", target_pair=target)
    state.close()
    
    await update.message.reply_text(
        f"🚨 <b>COMMAND LOGGED: STOP {target}</b>\n"
        f"Awaiting 10-second loop sweep...",
        parse_mode="HTML"
    )

@require_auth
async def bot_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/pause - Tells Ghost Trader to skip future entries."""
    state = GhostStateManager()
    state.write_command("/pause")
    state.close()
    await update.message.reply_text("⏳ <b>COMMAND LOGGED: PAUSE</b>", parse_mode="HTML")

@require_auth
async def bot_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/resume - Tells Ghost Trader to resume normal tick execution."""
    state = GhostStateManager()
    state.write_command("/resume")
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

def main():
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

    logging.info("Telegram UI Daemon Started. Listening for commands...")
    app.run_polling()

if __name__ == '__main__':
    main()
