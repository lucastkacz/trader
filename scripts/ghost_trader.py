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

import os
import json
import asyncio
import argparse
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from src.core.logger import logger, LogContext
from src.core.config import settings
from src.data.fetcher.live_client import fetch_live_klines
from src.engine.ghost.state_manager import GhostStateManager
from src.engine.ghost.signal_engine import evaluate_signal, BARS_PER_DAY

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


def load_tier1_pairs() -> List[Dict[str, Any]]:
    """Load surviving pairs and filter to Tier 1 (Sharpe >= configured threshold)."""
    path = "data/universes/surviving_pairs.json"
    with open(path, "r") as f:
        all_pairs = json.load(f)

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


async def execute_tick(pairs: List[Dict[str, Any]], state: GhostStateManager):
    """
    Execute a single 4H tick across all Tier 1 pairs.
    This is the core processing loop called once per candle close.
    """
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

        elif current_side is not None and result.signal == "FLAT":
            # EXIT: Position open → close it
            state.close_position(
                pair_label=pair_label,
                exit_price_a=result.price_a,
                exit_price_b=result.price_b,
            )

        elif current_side is not None and result.signal != "FLAT" and result.signal != current_side:
            # FLIP: Signal reversed → close then re-enter
            state.close_position(
                pair_label=pair_label,
                exit_price_a=result.price_a,
                exit_price_b=result.price_b,
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
        # else: HOLD — no action required

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
    args = parser.parse_args()
    TURBO_MODE = args.turbo

    mode_label = "TURBO (1m candles, 60s cycle)" if TURBO_MODE else "PRODUCTION (4H candles)"
    db_path = "data/ghost/trades_turbo.db" if TURBO_MODE else None  # None = use default from config

    logger.info("═══════════════════════════════════════════════════════════")
    logger.info(f"  EPOCH 3: Ghost Trader Starting [{mode_label}]")
    logger.info("═══════════════════════════════════════════════════════════")

    pairs = load_tier1_pairs()
    if not pairs:
        logger.error("No Tier 1 pairs found. Aborting.")
        return

    state = GhostStateManager(db_path=db_path)

    # Report existing state on boot
    open_pos = state.get_open_positions()
    if open_pos:
        logger.info(f"Resuming with {len(open_pos)} open ghost positions from previous session.")

    tick_count = 0

    try:
        while True:
            if TURBO_MODE:
                sleep_seconds = TURBO_SLEEP_SECONDS
                logger.info(f"[TURBO] Sleeping {sleep_seconds}s before tick {tick_count + 1}/{TURBO_MAX_TICKS}...")
            else:
                sleep_seconds = seconds_until_next_candle()
                next_wake = datetime.now(timezone.utc) + timedelta(seconds=sleep_seconds)
                logger.info(
                    f"Sleeping {sleep_seconds:.0f}s until next 4H candle "
                    f"(wake @ {next_wake.strftime('%Y-%m-%d %H:%M:%S')} UTC)"
                )

            await asyncio.sleep(sleep_seconds)
            await execute_tick(pairs, state)
            tick_count += 1

            if TURBO_MODE and tick_count >= TURBO_MAX_TICKS:
                logger.info(f"[TURBO] Completed {TURBO_MAX_TICKS} ticks. Auto-stopping.")
                break

    except KeyboardInterrupt:
        logger.info("Ghost Trader shut down by user (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"Ghost Trader crashed: {e}")
        raise
    finally:
        state.close()
        logger.info("Database connection closed cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
