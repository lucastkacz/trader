"""
Epoch 3: Ghost Trader Orchestrator
====================================
Long-running async process that wakes every 4H aligned to candle closes,
generates signals for the Tier 1 surviving pairs, and records phantom trades
into a local SQLite database.

Exchange-agnostic: reads live prices from whichever exchange is configured
in .env (GHOST_EXCHANGE=bybit or binance).

Designed for deployment via systemd on a VPS or launchd locally.
"""

import json
import asyncio
import argparse
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from src.core.logger import logger
from src.core.config import settings
from src.data.fetcher.live_client import fetch_live_klines
from src.engine.ghost.state_manager import GhostStateManager
from src.engine.ghost.signal_engine import evaluate_signal, BARS_PER_DAY
from src.core.notifier import TelegramNotifier

# ─── Mode Configuration ──────────────────────────────────────────
# Set by CLI --turbo flag. Controls timeframe, sleep, and DB path.
TURBO_MODE = False

# Production: 4H candles, sleep until next 4H boundary
# Turbo:      1m candles, sleep 60 seconds between ticks
CANDLE_HOURS = [0, 4, 8, 12, 16, 20]
CANDLE_BUFFER_SECONDS = 30
TURBO_SLEEP_SECONDS = 60
TURBO_TIMEFRAME = "1m"
TURBO_MAX_TICKS = 5  # Auto-stop after N ticks in turbo mode
PRODUCTION_TIMEFRAME = "4h"

# Hardcoded mega-cap pairs for CI/integration testing.
# Used when surviving_pairs.json doesn't exist (e.g. GitHub Actions).
# These are always liquid on every exchange — the signals are meaningless
# but the pipeline (fetch → signal → SQLite → report) is validated.
CI_FALLBACK_PAIRS = [
    {
        "Asset_X": "BTC/USDT", "Asset_Y": "ETH/USDT",
        "Best_Params": {"lookback_days": 14, "entry_z": 2.0},
        "Performance": {"sharpe_ratio": 99.0, "final_pnl_pct": 0.0},
    },
    {
        "Asset_X": "SOL/USDT", "Asset_Y": "LINK/USDT",
        "Best_Params": {"lookback_days": 14, "entry_z": 2.0},
        "Performance": {"sharpe_ratio": 99.0, "final_pnl_pct": 0.0},
    },
    {
        "Asset_X": "XRP/USDT", "Asset_Y": "ADA/USDT",
        "Best_Params": {"lookback_days": 14, "entry_z": 2.0},
        "Performance": {"sharpe_ratio": 99.0, "final_pnl_pct": 0.0},
    },
]


def load_tier1_pairs() -> List[Dict[str, Any]]:
    """Load surviving pairs and filter to Tier 1 (Sharpe >= configured threshold).
    Falls back to hardcoded mega-cap pairs when the file doesn't exist (CI)."""
    path = "data/universes/surviving_pairs.json"
    try:
        with open(path, "r") as f:
            all_pairs = json.load(f)
    except FileNotFoundError:
        logger.warning(
            f"surviving_pairs.json not found — using {len(CI_FALLBACK_PAIRS)} "
            f"CI fallback pairs (mega-caps for pipeline testing only)"
        )
        return CI_FALLBACK_PAIRS

    min_sharpe = settings.ghost_min_sharpe
    tier1 = [p for p in all_pairs if p["Performance"]["sharpe_ratio"] >= min_sharpe]

    logger.info(
        f"Loaded {len(tier1)} Tier 1 pairs (Sharpe >= {min_sharpe}) "
        f"from {len(all_pairs)} total survivors."
    )
    return tier1


def seconds_until_next_candle() -> float:
    """
    Calculate the number of seconds until the next 4H candle close + buffer.
    Binance 4H candles close at 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC.
    """
    now = datetime.now(timezone.utc)
    current_hour = now.hour

    # Find the next candle boundary
    next_candle_hour = None
    for h in CANDLE_HOURS:
        if h > current_hour:
            next_candle_hour = h
            break

    if next_candle_hour is None:
        # Past 20:00 UTC — next candle is 00:00 tomorrow
        next_candle = now.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
    else:
        next_candle = now.replace(
            hour=next_candle_hour, minute=0, second=0, microsecond=0
        )

    delta = (next_candle - now).total_seconds() + CANDLE_BUFFER_SECONDS
    return max(delta, 0)


async def fetch_recent_candles(symbol: str, bars_needed: int) -> pd.DataFrame:
    """
    Fetch the most recent N candles for a symbol from the configured exchange.
    Adds a symbol attribute for logging.
    """
    tf = TURBO_TIMEFRAME if TURBO_MODE else PRODUCTION_TIMEFRAME
    df = await fetch_live_klines(symbol=symbol, timeframe=tf, limit=bars_needed)
    df.attrs["symbol"] = symbol
    return df


def calculate_unrealized_pnl(
    state: GhostStateManager,
    pair_prices: Dict[str, tuple],
) -> float:
    """
    Calculate total unrealized PnL across all open positions using current prices.
    """
    open_positions = state.get_open_positions()
    total_unrealized = 0.0

    for pos in open_positions:
        label = pos["pair_label"]
        if label not in pair_prices:
            continue

        current_a, current_b = pair_prices[label]
        ret_a = (current_a - pos["entry_price_a"]) / pos["entry_price_a"]
        ret_b = (current_b - pos["entry_price_b"]) / pos["entry_price_b"]

        if pos["side"] == "LONG_SPREAD":
            unrealized = pos["weight_a"] * ret_a - pos["weight_b"] * ret_b
        else:
            unrealized = -pos["weight_a"] * ret_a + pos["weight_b"] * ret_b

        total_unrealized += unrealized

    return total_unrealized


def calculate_per_pair_pnl(
    state: GhostStateManager,
    pair_prices: Dict[str, tuple],
) -> Dict[str, float]:
    """
    Calculate per-pair unrealized PnL for each open position.
    Returns a dict of {pair_label: unrealized_pnl_pct}.
    """
    open_positions = state.get_open_positions()
    per_pair = {}

    for pos in open_positions:
        label = pos["pair_label"]
        if label not in pair_prices:
            continue

        current_a, current_b = pair_prices[label]
        ret_a = (current_a - pos["entry_price_a"]) / pos["entry_price_a"]
        ret_b = (current_b - pos["entry_price_b"]) / pos["entry_price_b"]

        if pos["side"] == "LONG_SPREAD":
            unrealized = pos["weight_a"] * ret_a - pos["weight_b"] * ret_b
        else:
            unrealized = -pos["weight_a"] * ret_a + pos["weight_b"] * ret_b

        per_pair[label] = unrealized

    return per_pair


def determine_action(current_side, new_signal) -> str:
    """
    Determine the action taken for tick_signals logging.
    ENTRY  — No position → opening one
    EXIT   — Position exists → signal says close
    HOLD   — Position exists → signal says keep same side
    SKIP   — No position → signal says stay flat
    FLIP   — Position exists → signal says opposite side (close + re-enter)
    """
    if current_side is None:
        if new_signal == "FLAT":
            return "SKIP"
        else:
            return "ENTRY"
    else:
        if new_signal == "FLAT":
            return "EXIT"
        elif new_signal == current_side:
            return "HOLD"
        else:
            return "FLIP"


SYSTEM_PAUSED = False

async def execute_emergency_liquidation(state: GhostStateManager, pairs: List[Dict], notifier: TelegramNotifier, target: Optional[str] = None):
    """Fetch live prices and force-close open positions."""
    open_positions = state.get_open_positions()
    
    if target:
        open_positions = [p for p in open_positions if p["pair_label"] == target]
        
    if not open_positions:
        if notifier:
            await notifier.send(f"⚠️ Liquidation requested but no positions found for <b>{target or 'ALL'}</b>.")
        return

    if notifier:
        await notifier.send(f"🚨 <b>EXECUTING EMERGENCY LIQUIDATION</b> for {len(open_positions)} pair(s)...")
        
    total_exit_pnl = 0.0
    for pos in open_positions:
        pair_label = pos["pair_label"]
        asset_x = pos["asset_x"]
        asset_y = pos["asset_y"]
        # Fetch 1 bar just to get current price
        try:
            df_x = await fetch_live_klines(symbol=asset_x, timeframe="1m", limit=1)
            df_y = await fetch_live_klines(symbol=asset_y, timeframe="1m", limit=1)
            price_x = df_x['close'].iloc[-1]
            price_y = df_y['close'].iloc[-1]
            
            pnl = state.close_position(
                pair_label=pair_label,
                exit_price_a=price_x,
                exit_price_b=price_y,
                exit_z=None  # manual exit
            )
            total_exit_pnl += pnl or 0.0
            if notifier:
                await notifier.send(f"✅ <b>EMERGENCY EXIT:</b> {pair_label}\nPNL: <b>{pnl*100:.2f}%</b>")
        except Exception as e:
            logger.error(f"Liquidation failed for {pair_label}: {e}")
            if notifier:
                await notifier.send(f"❌ LIQUIDATION FAILED for {pair_label}: {e}")

async def process_user_commands(state: GhostStateManager, pairs: List[Dict], notifier: TelegramNotifier):
    """Poll DB for Telegram commands and execute them."""
    global SYSTEM_PAUSED
    commands = state.pop_pending_commands()
    for cmd in commands:
        action = cmd["command"]
        target = cmd["target_pair"]
        logger.info(f"Processing UI Command: {action} on {target}")
        
        try:
            if action == "/stop_all":
                await execute_emergency_liquidation(state, pairs, notifier, target=None)
            elif action == "/stop":
                await execute_emergency_liquidation(state, pairs, notifier, target=target)
            elif action == "/pause":
                SYSTEM_PAUSED = True
                if notifier:
                    await notifier.send("⏸️ <b>SYSTEM PAUSED</b>\nNo new trades will be executed.")
            elif action == "/resume":
                SYSTEM_PAUSED = False
                if notifier:
                    await notifier.send("▶️ <b>SYSTEM RESUMED</b>\nTick execution restored.")
            else:
                logger.warning(f"Unknown command {action}")
        except Exception as e:
            logger.error(f"Failed executing command {action}: {e}")
            if notifier:
                await notifier.send(f"⚠️ COMMAND FAILED: {action} ({e})")


async def execute_tick(pairs: List[Dict[str, Any]], state: GhostStateManager, notifier: TelegramNotifier):
    """
    Execute a single 4H tick across all Tier 1 pairs.
    This is the core processing loop called once per candle close.
    """
    global SYSTEM_PAUSED
    if SYSTEM_PAUSED:
        logger.info("Tick skipped — System is PAUSED.")
        return

    tick_time = datetime.now(timezone.utc).isoformat()
    logger.info(f"═══ GHOST TICK @ {tick_time} ═══")

    pair_prices = {}

    for pair in pairs:
        asset_x = pair["Asset_X"]
        asset_y = pair["Asset_Y"]
        pair_label = f"{asset_x}|{asset_y}"
        best_params = pair["Best_Params"]
        lookback_days = best_params["lookback_days"]
        entry_z = best_params["entry_z"]

        # We need enough bars for: lookback + volatility window + warm-up buffer
        bars_needed = max(lookback_days, 14) * BARS_PER_DAY + 50

        try:
            df_a = await fetch_recent_candles(asset_x, bars_needed)
            df_b = await fetch_recent_candles(asset_y, bars_needed)
        except Exception as e:
            logger.warning(f"Failed fetching data for {pair_label}: {e}")
            continue

        # Check current position state
        current_pos = state.get_position_for_pair(pair_label)
        current_side = current_pos["side"] if current_pos else None

        # Generate signal
        result = evaluate_signal(
            df_a=df_a,
            df_b=df_b,
            entry_z=entry_z,
            exit_z=0.0,
            lookback_days=lookback_days,
            current_side=current_side,
        )

        pair_prices[pair_label] = (result.price_a, result.price_b)

        # Determine action for tick_signals
        action = determine_action(current_side, result.signal)

        # Record tick signal for every pair on every tick
        state.record_tick_signal(
            pair_label=pair_label,
            z_score=result.z_score,
            weight_a=result.weight_a,
            weight_b=result.weight_b,
            signal=result.signal,
            action=action,
            price_a=result.price_a,
            price_b=result.price_b,
        )

        # State machine transitions
        if current_side is None and result.signal != "FLAT":
            # ENTRY: No position → open one
            state.open_position(
                pair_label=pair_label,
                asset_x=asset_x,
                asset_y=asset_y,
                side=result.signal,
                entry_price_a=result.price_a,
                entry_price_b=result.price_b,
                weight_a=result.weight_a,
                weight_b=result.weight_b,
                entry_z=result.z_score,
                lookback_days=lookback_days,
            )
            await notifier.send(
                f"🚀 <b>ENTRY SIGNAL: {pair_label}</b>\n"
                f"• Z-Score: {result.z_score:.2f}\n"
                f"• Action: {result.signal}"
            )

        elif current_side is not None and result.signal == "FLAT":
            # EXIT: Position open → close it
            pnl = state.close_position(
                pair_label=pair_label,
                exit_price_a=result.price_a,
                exit_price_b=result.price_b,
                exit_z=result.z_score,
            )
            await notifier.send(
                f"🏁 <b>EXIT SIGNAL: {pair_label}</b>\n"
                f"• Z-Score: {result.z_score:.2f}\n"
                f"• PNL: <b>{pnl*100:.2f}%</b> if pnl else 'N/A'\n"
                f"• Action: CLOSE Spread"
            )

        elif current_side is not None and result.signal != "FLAT" and result.signal != current_side:
            # FLIP: Signal reversed → close then re-enter
            pnl = state.close_position(
                pair_label=pair_label,
                exit_price_a=result.price_a,
                exit_price_b=result.price_b,
                exit_z=result.z_score,
            )
            state.open_position(
                pair_label=pair_label,
                asset_x=asset_x,
                asset_y=asset_y,
                side=result.signal,
                entry_price_a=result.price_a,
                entry_price_b=result.price_b,
                weight_a=result.weight_a,
                weight_b=result.weight_b,
                entry_z=result.z_score,
                lookback_days=lookback_days,
            )
            await notifier.send(
                f"🔄 <b>FLIP SIGNAL: {pair_label}</b>\n"
                f"• Old Side Closed | PNL: <b>{pnl*100:.2f}%</b> if pnl else 'N/A'\n"
                f"• New Side: {result.signal}\n"
                f"• Z-Score: {result.z_score:.2f}"
            )
        # else: HOLD — no action required

    # Per-pair PnL for equity snapshot
    per_pair_pnl = calculate_per_pair_pnl(state, pair_prices)
    per_pair_pnl_json = json.dumps(per_pair_pnl) if per_pair_pnl else None

    # Equity Snapshot
    closed = state.get_all_closed()
    realized = sum(t["pnl_pct"] or 0.0 for t in closed)
    unrealized = calculate_unrealized_pnl(state, pair_prices)
    open_count = len(state.get_open_positions())

    state.snapshot_equity(
        total_equity_pct=realized + unrealized,
        open_positions=open_count,
        realized_pnl_pct=realized,
        unrealized_pnl_pct=unrealized,
        per_pair_pnl=per_pair_pnl_json,
    )

    logger.info(
        f"Tick complete | Open: {open_count} | "
        f"Realized: {realized*100:.4f}% | Unrealized: {unrealized*100:.4f}% | "
        f"Total Equity: {(realized+unrealized)*100:.4f}%"
    )


async def main():
    global TURBO_MODE

    parser = argparse.ArgumentParser(description="Epoch 3: Ghost Trader")
    parser.add_argument(
        "--turbo", action="store_true",
        help="Turbo mode: 1m candles, 60s sleep, auto-stop after 5 ticks. For integration testing only."
    )
    parser.add_argument(
        "--ticks", type=int, default=None,
        help="Auto-stop after N ticks. Works in both turbo and production mode. "
             "If omitted: turbo defaults to 5, production runs forever."
    )
    args = parser.parse_args()
    TURBO_MODE = args.turbo

    # Determine max ticks: explicit --ticks > turbo default (5) > unlimited (None)
    max_ticks = args.ticks if args.ticks is not None else (TURBO_MAX_TICKS if TURBO_MODE else None)

    if TURBO_MODE:
        mode_label = "TURBO (1m candles, 60s cycle)"
    elif max_ticks is not None:
        mode_label = f"VALIDATION (4H candles, {max_ticks} ticks)"
    else:
        mode_label = "PRODUCTION (4H candles)"
    db_path = "data/ghost/trades_turbo.db" if TURBO_MODE else None  # None = use default from config

    logger.info("═══════════════════════════════════════════════════════════")
    logger.info(f"  EPOCH 3: Ghost Trader Starting [{mode_label}]")
    logger.info("═══════════════════════════════════════════════════════════")

    notifier = TelegramNotifier()
    await notifier.send(f"🟢 <b>System Boot:</b> Engine Synchronized on {mode_label}")

    pairs = load_tier1_pairs()
    if not pairs:
        logger.error("No Tier 1 pairs found. Aborting.")
        await notifier.send("⚠️ <b>Fatal Error:</b> No Tier 1 pairs found.")
        return

    state = GhostStateManager(db_path=db_path)

    # Report existing state on boot
    open_pos = state.get_open_positions()
    if open_pos:
        logger.info(f"Resuming with {len(open_pos)} open ghost positions.")

    tick_count = 0
    ticks_label = f"/{max_ticks}" if max_ticks else ""

    try:
        while True:
            # Set target wake time
            if TURBO_MODE:
                sleep_seconds = TURBO_SLEEP_SECONDS
                target_time = datetime.now(timezone.utc) + timedelta(seconds=sleep_seconds)
            else:
                sleep_seconds = seconds_until_next_candle()
                target_time = datetime.now(timezone.utc) + timedelta(seconds=sleep_seconds)
                
            wake_fmt = target_time.strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"Next tick scheduled for {wake_fmt} UTC. Entering polling loop.")
            
            # Polling loop (Wait in 10-second chunks to process commands)
            while True:
                await process_user_commands(state, pairs, notifier)
                
                now = datetime.now(timezone.utc)
                if now >= target_time:
                    break
                    
                await asyncio.sleep(min(10.0, (target_time - now).total_seconds()))

            # Execution
            await execute_tick(pairs, state, notifier)
            tick_count += 1

            if max_ticks is not None and tick_count >= max_ticks:
                logger.info(f"Completed {max_ticks} ticks. Auto-stopping.")
                break

    except KeyboardInterrupt:
        logger.info("Ghost Trader shut down by user (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"Ghost Trader crashed: {e}")
        await notifier.send(f"⚠️ <b>FATAL ERROR:</b> Ghost Trader crashed:\n<pre>{e}</pre>")
        raise
    finally:
        state.close()
        logger.info("Database connection closed cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
