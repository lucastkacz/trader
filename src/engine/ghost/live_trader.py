import json
import asyncio
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from src.core.logger import logger
from src.data.fetcher.live_client import fetch_live_klines
from src.engine.ghost.state_manager import GhostStateManager
from src.engine.ghost.signal_engine import evaluate_signal
from src.core.notifier import TelegramNotifier

class LiveGhostTrader:
    def __init__(self):
        pass

    def load_tier1_pairs(self, timeframe: str, min_sharpe: float) -> List[Dict[str, Any]]:
        path = f"data/universes/{timeframe}/surviving_pairs.json"
        with open(path, "r") as f:
            all_pairs = json.load(f)

        tier1 = [p for p in all_pairs if p.get("Performance", {}).get("sharpe_ratio", 0) >= min_sharpe]

        logger.info(
            f"Loaded {len(tier1)} Tier 1 pairs (Sharpe >= {min_sharpe}) "
            f"from {len(all_pairs)} total survivors."
        )
        return tier1

    def seconds_until_next_candle(self, timeframe: str) -> float:
        now = datetime.now(timezone.utc)
        CANDLE_BUFFER_SECONDS = 30
        
        if timeframe.endswith('h'):
            hours = int(timeframe[:-1])
            next_hour = ((now.hour // hours) + 1) * hours
            if next_hour >= 24:
                next_candle = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            else:
                next_candle = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
        elif timeframe.endswith('m'):
            minutes = int(timeframe[:-1])
            next_minute = ((now.minute // minutes) + 1) * minutes
            if next_minute >= 60:
                next_candle = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            else:
                next_candle = now.replace(minute=next_minute, second=0, microsecond=0)
        else:
            return 60.0 
            
        delta = (next_candle - now).total_seconds() + CANDLE_BUFFER_SECONDS
        return max(delta, 0)

    async def fetch_recent_candles(self, symbol: str, bars_needed: int, timeframe: str) -> pd.DataFrame:
        df = await fetch_live_klines(symbol=symbol, timeframe=timeframe, limit=bars_needed)
        df.attrs["symbol"] = symbol
        return df

    def calculate_unrealized_pnl(self, state: GhostStateManager, pair_prices: Dict[str, tuple]) -> float:
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

    def calculate_per_pair_pnl(self, state: GhostStateManager, pair_prices: Dict[str, tuple]) -> Dict[str, float]:
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

    def determine_action(self, current_side, new_signal) -> str:
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

    async def execute_emergency_liquidation(self, state: GhostStateManager, pairs: List[Dict], notifier: TelegramNotifier, timeframe: str, target: Optional[str] = None):
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
            try:
                df_x = await self.fetch_recent_candles(symbol=asset_x, timeframe=timeframe, bars_needed=1)
                df_y = await self.fetch_recent_candles(symbol=asset_y, timeframe=timeframe, bars_needed=1)
                price_x = df_x['close'].iloc[-1]
                price_y = df_y['close'].iloc[-1]
                
                pnl = state.close_position(
                    pair_label=pair_label,
                    exit_price_a=price_x,
                    exit_price_b=price_y,
                    exit_z=None
                )
                total_exit_pnl += pnl or 0.0
                if notifier:
                    await notifier.send(f"✅ <b>EMERGENCY EXIT:</b> {pair_label}\nPNL: <b>{pnl*100:.2f}%</b>")
            except Exception as e:
                logger.error(f"Liquidation failed for {pair_label}: {e}")
                if notifier:
                    await notifier.send(f"❌ LIQUIDATION FAILED for {pair_label}: {e}")

    async def process_user_commands(self, state: GhostStateManager, pairs: List[Dict], notifier: TelegramNotifier, timeframe: str):
        global SYSTEM_PAUSED
        commands = state.pop_pending_commands()
        for cmd in commands:
            action = cmd["command"]
            target = cmd["target_pair"]
            logger.info(f"Processing UI Command: {action} on {target}")
            
            try:
                if action == "/stop_all":
                    await self.execute_emergency_liquidation(state, pairs, notifier, timeframe, target=None)
                elif action == "/stop":
                    await self.execute_emergency_liquidation(state, pairs, notifier, timeframe, target=target)
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


    async def execute_tick(self, pairs: List[Dict[str, Any]], state: GhostStateManager, notifier: TelegramNotifier, timeframe: str, strategy_cfg: dict):
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
            lookback_bars = best_params["lookback_bars"]
            entry_z = best_params["entry_z"]
            vol_lookback_bars = strategy_cfg["execution"]["volatility_lookback_bars"]

            bars_needed = lookback_bars + 50

            try:
                df_a = await self.fetch_recent_candles(asset_x, bars_needed, timeframe)
                df_b = await self.fetch_recent_candles(asset_y, bars_needed, timeframe)
            except Exception as e:
                logger.warning(f"Failed fetching data for {pair_label}: {e}")
                continue

            current_pos = state.get_position_for_pair(pair_label)
            current_side = current_pos["side"] if current_pos else None

            exit_z = strategy_cfg["execution"]["exit_z_score"]

            result = evaluate_signal(
                df_a=df_a,
                df_b=df_b,
                entry_z=entry_z,
                exit_z=exit_z,
                lookback_bars=lookback_bars,
                vol_lookback_bars=vol_lookback_bars,
                current_side=current_side,
            )

            pair_prices[pair_label] = (result.price_a, result.price_b)

            action = self.determine_action(current_side, result.signal)

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

            if current_side is None and result.signal != "FLAT":
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
                    lookback_bars=lookback_bars,
                )
                await notifier.send(
                    f"🚀 <b>ENTRY SIGNAL: {pair_label}</b>\n"
                    f"• Z-Score: {result.z_score:.2f}\n"
                    f"• Action: {result.signal}"
                )

            elif current_side is not None and result.signal == "FLAT":
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
                    lookback_bars=lookback_bars,
                )
                await notifier.send(
                    f"🔄 <b>FLIP SIGNAL: {pair_label}</b>\n"
                    f"• Old Side Closed | PNL: <b>{pnl*100:.2f}%</b> if pnl else 'N/A'\n"
                    f"• New Side: {result.signal}\n"
                    f"• Z-Score: {result.z_score:.2f}"
                )

        per_pair_pnl = self.calculate_per_pair_pnl(state, pair_prices)
        per_pair_pnl_json = json.dumps(per_pair_pnl) if per_pair_pnl else None

        closed = state.get_all_closed()
        realized = sum(t["pnl_pct"] or 0.0 for t in closed)
        unrealized = self.calculate_unrealized_pnl(state, pair_prices)
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


    async def run(self, pipeline_cfg: dict, strategy_cfg: dict, notifier: TelegramNotifier = None):
        timeframe = pipeline_cfg["timeframe"]
        execution_cfg = pipeline_cfg["execution"]
        max_ticks = execution_cfg.get("max_ticks", None) # Optional loop limit
        heartbeat_seconds = execution_cfg["heartbeat_seconds"]
        sync_to_boundary = execution_cfg["sync_to_boundary"]
        db_path = execution_cfg["db_path"]
        min_sharpe = execution_cfg["min_sharpe"]

        logger.info("═══════════════════════════════════════════════════════════")
        logger.info(f"  EPOCH 3: Ghost Trader Starting [{timeframe}]")
        logger.info(f"  Sync: {sync_to_boundary} | Heartbeat: {heartbeat_seconds}s")
        logger.info("═══════════════════════════════════════════════════════════")

        if notifier is None:
            notifier = TelegramNotifier()
            
        await notifier.send(f"🟢 <b>System Boot:</b> Engine Synchronized on {timeframe}")

        pairs = self.load_tier1_pairs(timeframe, min_sharpe)
        if not pairs:
            logger.error("No Tier 1 pairs found. Aborting.")
            await notifier.send("⚠️ <b>Fatal Error:</b> No Tier 1 pairs found.")
            return

        state = GhostStateManager(db_path=db_path)

        open_pos = state.get_open_positions()
        if open_pos:
            logger.info(f"Resuming with {len(open_pos)} open ghost positions.")

        tick_count = 0

        try:
            while True:
                if sync_to_boundary:
                    sleep_seconds = self.seconds_until_next_candle(timeframe)
                else:
                    sleep_seconds = heartbeat_seconds
                    
                target_time = datetime.now(timezone.utc) + timedelta(seconds=sleep_seconds)
                wake_fmt = target_time.strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"Next tick scheduled for {wake_fmt} UTC. Entering polling loop.")
                
                while True:
                    await self.process_user_commands(state, pairs, notifier, timeframe)
                    
                    now = datetime.now(timezone.utc)
                    if now >= target_time:
                        break
                        
                    await asyncio.sleep(min(10.0, (target_time - now).total_seconds()))

                await self.execute_tick(pairs, state, notifier, timeframe, strategy_cfg)
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
