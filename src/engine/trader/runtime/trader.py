"""Live trader runtime orchestration."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from src.core.config import settings
from src.core.logger import logger
from src.engine.trader.commands.processor import process_user_commands
from src.engine.trader.config import OrderExecutionConfig, PipelineConfig, RiskConfig, StrategyConfig
from src.engine.trader.execution.liquidation import execute_emergency_liquidation
from src.engine.trader.execution.market_data import fetch_recent_candles
from src.engine.trader.execution.orders import (
    CCXTOrderExecutionAdapter,
    OrderExecutionAdapter,
)
from src.engine.trader.execution.pnl import calculate_per_pair_pnl, calculate_unrealized_pnl
from src.engine.trader.reconciliation import (
    ExchangeSnapshotProvider,
    ReconciliationAuditReport,
    run_boot_reconciliation,
    run_read_only_audit,
)
from src.engine.trader.runtime.actions import determine_action
from src.engine.trader.runtime.credentials import resolve_credentials
from src.engine.trader.runtime.pairs import load_tier1_pairs
from src.engine.trader.runtime.scheduler import seconds_until_next_candle
from src.engine.trader.runtime.tick import execute_tick
from src.engine.trader.state_manager import TradeStateManager
from src.interfaces.telegram.notifier import TelegramNotifier


class LiveTrader:
    """High-level trader runtime orchestrator."""

    def load_tier1_pairs(self, timeframe: str, min_sharpe: float) -> list[dict[str, Any]]:
        return load_tier1_pairs(timeframe, min_sharpe)

    def seconds_until_next_candle(self, timeframe: str) -> float:
        return seconds_until_next_candle(timeframe)

    async def fetch_recent_candles(
        self,
        symbol: str,
        bars_needed: int,
        timeframe: str,
        exchange_id: str,
        api_key: str,
        api_secret: str,
    ):
        return await fetch_recent_candles(
            symbol=symbol,
            bars_needed=bars_needed,
            timeframe=timeframe,
            exchange_id=exchange_id,
            api_key=api_key,
            api_secret=api_secret,
        )

    def calculate_unrealized_pnl(
        self,
        state: TradeStateManager,
        pair_prices: dict[str, tuple[float, float]],
    ) -> float:
        return calculate_unrealized_pnl(state, pair_prices)

    def calculate_per_pair_pnl(
        self,
        state: TradeStateManager,
        pair_prices: dict[str, tuple[float, float]],
    ) -> dict[str, float]:
        return calculate_per_pair_pnl(state, pair_prices)

    def determine_action(self, current_side: str | None, new_signal: str) -> str:
        return determine_action(current_side, new_signal)

    async def execute_emergency_liquidation(
        self,
        state: TradeStateManager,
        pairs: list[dict[str, Any]],
        notifier: TelegramNotifier,
        timeframe: str,
        exchange_id: str,
        api_key: str,
        api_secret: str,
        target: str | None = None,
    ) -> None:
        await execute_emergency_liquidation(
            state=state,
            pairs=pairs,
            notifier=notifier,
            timeframe=timeframe,
            exchange_id=exchange_id,
            api_key=api_key,
            api_secret=api_secret,
            target=target,
        )

    async def process_user_commands(
        self,
        state: TradeStateManager,
        pairs: list[dict[str, Any]],
        notifier: TelegramNotifier,
        timeframe: str,
        exchange_id: str,
        api_key: str,
        api_secret: str,
    ) -> None:
        await process_user_commands(
            state=state,
            pairs=pairs,
            notifier=notifier,
            timeframe=timeframe,
            exchange_id=exchange_id,
            api_key=api_key,
            api_secret=api_secret,
        )

    async def execute_tick(
        self,
        pairs: list[dict[str, Any]],
        state: TradeStateManager,
        notifier: TelegramNotifier,
        timeframe: str,
        strategy_cfg: dict[str, Any],
        exchange_id: str,
        api_key: str,
        api_secret: str,
        order_execution_cfg: OrderExecutionConfig,
        order_execution_adapter: OrderExecutionAdapter | None,
    ) -> None:
        await execute_tick(
            pairs=pairs,
            state=state,
            notifier=notifier,
            timeframe=timeframe,
            strategy_cfg=strategy_cfg,
            exchange_id=exchange_id,
            api_key=api_key,
            api_secret=api_secret,
            order_execution_cfg=order_execution_cfg,
            order_execution_adapter=order_execution_adapter,
        )

    async def run_read_only_audit(
        self,
        state: TradeStateManager,
        snapshot_provider: ExchangeSnapshotProvider | None,
        credentials_available: bool,
        qty_tolerance: float = 1e-9,
    ) -> ReconciliationAuditReport:
        """Run one manually callable read-only reconciliation audit."""
        return await run_read_only_audit(
            state=state,
            snapshot_provider=snapshot_provider,
            credentials_available=credentials_available,
            qty_tolerance=qty_tolerance,
        )

    async def run(
        self,
        pipeline_cfg: PipelineConfig,
        strategy_cfg: StrategyConfig,
        risk_cfg: RiskConfig,
        reconciliation_snapshot_provider: ExchangeSnapshotProvider | None = None,
        notifier: TelegramNotifier = None,
    ) -> None:
        timeframe = pipeline_cfg.timeframe
        execution_cfg = pipeline_cfg.execution
        max_ticks = execution_cfg.max_ticks
        heartbeat_seconds = execution_cfg.heartbeat_seconds
        sync_to_boundary = execution_cfg.sync_to_boundary
        db_path = execution_cfg.db_path
        min_sharpe = execution_cfg.min_sharpe
        exchange_id = execution_cfg.exchange
        order_execution_cfg = execution_cfg.order_execution

        api_key, api_secret = resolve_credentials(
            settings=settings,
            credential_tier=execution_cfg.credential_tier,
        )
        if order_execution_cfg.mode == "live" and execution_cfg.credential_tier != "live":
            raise ValueError("order_execution.mode='live' requires credential_tier='live'")
        if order_execution_cfg.mode == "live" and not (api_key and api_secret):
            raise ValueError("order_execution.mode='live' requires live API credentials")
        order_execution_adapter = None
        if order_execution_cfg.mode == "live":
            order_execution_adapter = CCXTOrderExecutionAdapter(
                exchange_id=exchange_id,
                api_key=api_key,
                api_secret=api_secret,
            )

        logger.info("═══════════════════════════════════════════════════════════")
        logger.info(f"  Trader Engine Starting [{timeframe}]")
        logger.info(f"  Sync: {sync_to_boundary} | Heartbeat: {heartbeat_seconds}s")
        logger.info(
            f"  Risk: {risk_cfg.name} | "
            f"Cluster Cap: {risk_cfg.max_cluster_exposure:.2%} | "
            f"Max Leverage: {risk_cfg.max_leverage:.2f}x"
        )
        logger.info("═══════════════════════════════════════════════════════════")

        if notifier is None:
            notifier = TelegramNotifier()

        await notifier.send(f"🟢 <b>System Boot:</b> Engine Synchronized on {timeframe}")

        pairs = self.load_tier1_pairs(timeframe, min_sharpe)
        if not pairs:
            logger.error("No Tier 1 pairs found. Aborting.")
            await notifier.send("⚠️ <b>Fatal Error:</b> No Tier 1 pairs found.")
            return

        state = TradeStateManager(db_path=db_path)

        reconciliation_run_id = await run_boot_reconciliation(
            state=state,
            snapshot_provider=reconciliation_snapshot_provider,
            credentials_available=bool(api_key and api_secret),
        )
        reconciliation_run = next(
            run for run in state.get_reconciliation_runs()
            if run["id"] == reconciliation_run_id
        )
        reconciliation_status = reconciliation_run["status"]
        reconciliation_delta_count = len(
            state.get_reconciliation_deltas(run_id=reconciliation_run_id)
        )
        if reconciliation_status != "MATCHED":
            logger.warning(
                f"Boot reconciliation status={reconciliation_status} "
                f"deltas={reconciliation_delta_count}. No actions taken."
            )
            await notifier.send(
                f"⚠️ <b>Boot Reconciliation:</b> {reconciliation_status}\n"
                f"Deltas: {reconciliation_delta_count}\n"
                "Mode: read-only, no actions taken."
            )

        open_pos = state.get_open_positions()
        if open_pos:
            logger.info(f"Resuming with {len(open_pos)} open positions.")

        tick_count = 0

        try:
            while True:
                if sync_to_boundary:
                    sleep_seconds = self.seconds_until_next_candle(timeframe)
                else:
                    sleep_seconds = heartbeat_seconds

                target_time = datetime.now(timezone.utc) + timedelta(seconds=sleep_seconds)
                wake_fmt = target_time.strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"Next tick scheduled for {wake_fmt} UTC. Entering polling loop.")

                while True:
                    await self.process_user_commands(
                        state,
                        pairs,
                        notifier,
                        timeframe,
                        exchange_id=exchange_id,
                        api_key=api_key,
                        api_secret=api_secret,
                    )

                    now = datetime.now(timezone.utc)
                    if now >= target_time:
                        break

                    await asyncio.sleep(min(10.0, (target_time - now).total_seconds()))

                await self.execute_tick(
                    pairs,
                    state,
                    notifier,
                    timeframe,
                    strategy_cfg.model_dump(),
                    exchange_id=exchange_id,
                    api_key=api_key,
                    api_secret=api_secret,
                    order_execution_cfg=order_execution_cfg,
                    order_execution_adapter=order_execution_adapter,
                )
                tick_count += 1

                if max_ticks is not None and tick_count >= max_ticks:
                    logger.info(f"Completed {max_ticks} ticks. Auto-stopping.")
                    break

        except KeyboardInterrupt:
            logger.info("Trader Engine shut down by user (KeyboardInterrupt).")
        except Exception as exc:
            logger.critical(f"Trader Engine crashed: {exc}")
            await notifier.send(f"⚠️ <b>FATAL ERROR:</b> Trader Engine crashed:\n<pre>{exc}</pre>")
            raise
        finally:
            state.close()
            logger.info("Database connection closed cleanly.")
