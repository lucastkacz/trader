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
from datetime import datetime, timezone
from typing import Optional

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from src.core.config import settings
from src.engine.trader.config import TelegramConfig
from src.engine.trader.config import load_telegram_config as load_typed_telegram_config
from src.engine.trader.reporting.position_inspector import (
    PositionInspection,
    inspect_open_position,
)
from src.engine.trader.state_manager import TradeStateManager

# Minimal basic logging for the listener itself
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

TELEGRAM_DB_PATH: Optional[str] = None
TELEGRAM_ENVIRONMENT: Optional[str] = None
TELEGRAM_HOLDING_PERIOD_BAR_MINUTES: Optional[float] = None


def configure_daemon(config_path: str) -> TelegramConfig:
    """Configure daemon process globals from YAML."""
    global TELEGRAM_DB_PATH, TELEGRAM_ENVIRONMENT, TELEGRAM_HOLDING_PERIOD_BAR_MINUTES
    cfg = load_typed_telegram_config(config_path)
    TELEGRAM_DB_PATH = cfg.db_path
    TELEGRAM_ENVIRONMENT = cfg.environment
    TELEGRAM_HOLDING_PERIOD_BAR_MINUTES = cfg.holding_period_bar_minutes
    return cfg


def open_state_manager() -> TradeStateManager:
    """Open a short-lived state connection for one command handler."""
    if TELEGRAM_DB_PATH is None:
        raise RuntimeError("Telegram daemon db_path is not configured")
    return TradeStateManager(db_path=TELEGRAM_DB_PATH)


def holding_duration_minutes(position: dict) -> float:
    """Return display duration in minutes using explicit Telegram bar policy."""
    if TELEGRAM_HOLDING_PERIOD_BAR_MINUTES is None:
        raise RuntimeError("Telegram daemon holding_period_bar_minutes is not configured")

    holding_bars = position.get("holding_bars")
    if holding_bars:
        return holding_bars * TELEGRAM_HOLDING_PERIOD_BAR_MINUTES

    opened_at = position.get("opened_at")
    if not opened_at:
        return 0.0

    try:
        t_open = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return 0.0
    return max(0.0, (datetime.now(timezone.utc) - t_open).total_seconds() / 60.0)


def format_duration(minutes: float) -> str:
    """Format a holding duration for compact Telegram display."""
    if minutes < 60:
        return f"{minutes:.0f}m"
    return f"{minutes / 60.0:g}h"


def format_pct(value: float | None) -> str:
    """Format a decimal percentage for Telegram display."""
    if value is None:
        return "N/A"
    return f"{value * 100:+.2f}%"


def format_price(value: float | None) -> str:
    """Format an asset price for compact Telegram display."""
    if value is None:
        return "N/A"
    return f"{value:.6g}"


def format_z(value: float | None) -> str:
    """Format a z-score for compact Telegram display."""
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def format_leg_statuses(status_counts: dict[str, dict[str, int]]) -> str:
    """Format leg lifecycle counts by role."""
    if not status_counts:
        return "none"
    parts = []
    for role, counts in status_counts.items():
        summary = ", ".join(f"{status} x{count}" for status, count in counts.items())
        parts.append(f"{role}: {summary}")
    return "\n".join(parts)


def render_position_inspection(inspection: PositionInspection) -> str:
    """Render one position inspection snapshot as a Telegram HTML message."""
    position = inspection.position
    latest = inspection.latest_signal or {}
    duration = format_duration(holding_duration_minutes(position))
    mark_label = "Latest Recorded Mark" if inspection.latest_signal else "Latest Recorded Mark"
    current_price_a = latest.get("price_a")
    current_price_b = latest.get("price_b")

    return (
        f"🔎 <b>POSITION INSPECTOR #{position['id']}</b>\n"
        f"Pair: <b>{position['pair_label']}</b>\n"
        f"Side: {position['side']}\n"
        f"Opened: {position['opened_at']}\n"
        f"Duration: {duration}\n\n"
        f"<b>Entry</b>\n"
        f"{position['asset_x']}: {format_price(position['entry_price_a'])}\n"
        f"{position['asset_y']}: {format_price(position['entry_price_b'])}\n"
        f"Entry Z: {format_z(position['entry_z'])}\n"
        f"Weights: {position['weight_a']:.2f} / {position['weight_b']:.2f}\n"
        f"Lookback: {position['lookback_bars']} bars\n\n"
        f"<b>{mark_label}</b>\n"
        f"{position['asset_x']}: {format_price(current_price_a)}\n"
        f"{position['asset_y']}: {format_price(current_price_b)}\n"
        f"Z-Score: {format_z(latest.get('z_score'))}\n"
        f"Signal: {latest.get('signal', 'N/A')}\n"
        f"Action: {latest.get('action', 'N/A')}\n"
        f"Signal Time: {latest.get('timestamp', 'N/A')}\n\n"
        f"<b>PnL</b>\n"
        f"Unrealized: {format_pct(inspection.unrealized_pnl)}\n\n"
        f"<b>Execution State</b>\n"
        f"{format_leg_statuses(inspection.leg_status_counts)}\n"
        f"Exchange/client IDs present: {'YES' if inspection.has_exchange_identifiers else 'NO'}"
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
        duration = format_duration(holding_duration_minutes(p))
        msg += f"• <b>#{p['id']} {p['pair_label']}</b> ({p['side']})\n"
        msg += f"  Duration: {duration}\n"
        
    await update.message.reply_text(msg, parse_mode="HTML")

@require_auth
async def bot_inspect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/inspect <ID|PAIR> - Shows detailed read-only state for one open position."""
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /inspect 1 or /inspect BTC/USDT|ETH/USDT")
        return

    identifier = " ".join(context.args).strip()
    state = open_state_manager()
    try:
        inspection = inspect_open_position(state, identifier)
    finally:
        state.close()

    if inspection is None:
        await update.message.reply_text(
            f"📭 No open position found for <code>{identifier}</code>.",
            parse_mode="HTML",
        )
        return

    await update.message.reply_text(render_position_inspection(inspection), parse_mode="HTML")

@require_auth
async def bot_stop_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stop_all - Instructs the Trader to immediately liquidate."""
    state = open_state_manager()
    try:
        state.write_command("/stop_all")
    finally:
        state.close()
    
    await update.message.reply_text(
        "🚨 <b>COMMAND LOGGED: LOCAL STATE STOP ALL</b>\n"
        "The executing trader will record forced local closes on its next command sweep.",
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
        f"🚨 <b>COMMAND LOGGED: LOCAL STATE STOP {target}</b>\n"
        "The executing trader will record a forced local close on its next command sweep.",
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
        "/inspect [ID|PAIR] - Deep read-only position view\n"
        "/pause - Skip new trades (Holds existing)\n"
        "/resume - Revert pause mechanism\n"
        "/stop [PAIR] - Requests one forced local-state close\n"
        "/stop_all - Requests forced local-state close for everything"
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
    app.add_handler(CommandHandler("inspect", bot_inspect))
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
