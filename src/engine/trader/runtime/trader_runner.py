"""Runtime loop implementation behind LiveTrader.run."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from src.core.config import settings
from src.core.logger import logger
from src.engine.trader.config import PipelineConfig, RiskConfig, StrategyConfig
from src.engine.trader.execution.orders import CCXTOrderExecutionAdapter
from src.engine.trader.reconciliation import ExchangeSnapshotProvider, run_boot_reconciliation
from src.engine.trader.runtime.credentials import resolve_credentials
from src.engine.trader.state_manager import TradeStateManager
from src.interfaces.telegram.notifier import TelegramNotifier


async def run_trader_loop(
    trader: Any,
    pipeline_cfg: PipelineConfig,
    strategy_cfg: StrategyConfig,
    risk_cfg: RiskConfig,
    reconciliation_snapshot_provider: ExchangeSnapshotProvider | None = None,
    notifier: TelegramNotifier | None = None,
) -> None:
    execution_cfg = pipeline_cfg.execution
    api_key, api_secret = resolve_credentials(settings, execution_cfg.credential_tier)
    order_adapter = _build_order_adapter(execution_cfg, api_key, api_secret)
    _log_startup(pipeline_cfg, risk_cfg)

    notifier = notifier or TelegramNotifier()
    await notifier.send(f"🟢 <b>System Boot:</b> Engine Synchronized on {pipeline_cfg.timeframe}")

    pairs = trader.load_tier1_pairs(
        pipeline_cfg.timeframe,
        execution_cfg.min_sharpe,
        execution_cfg.exchange,
        execution_cfg.artifact_base_dir,
    )
    if not pairs:
        logger.error("No Tier 1 pairs found. Aborting.")
        await notifier.send("⚠️ <b>Fatal Error:</b> No Tier 1 pairs found.")
        return

    state = TradeStateManager(db_path=execution_cfg.db_path)
    try:
        await _run_boot_reconciliation(state, reconciliation_snapshot_provider, api_key, api_secret, notifier)
        await _run_ticks(
            trader=trader,
            state=state,
            pairs=pairs,
            pipeline_cfg=pipeline_cfg,
            strategy_cfg=strategy_cfg,
            notifier=notifier,
            api_key=api_key,
            api_secret=api_secret,
            order_adapter=order_adapter,
        )
    except KeyboardInterrupt:
        logger.info("Trader Engine shut down by user (KeyboardInterrupt).")
    except Exception as exc:
        logger.critical(f"Trader Engine crashed: {exc}")
        await notifier.send(f"⚠️ <b>FATAL ERROR:</b> Trader Engine crashed:\n<pre>{exc}</pre>")
        raise
    finally:
        state.close()
        logger.info("Database connection closed cleanly.")


def _build_order_adapter(execution_cfg, api_key: str, api_secret: str):
    order_execution_cfg = execution_cfg.order_execution
    if order_execution_cfg.mode == "live" and execution_cfg.credential_tier != "live":
        raise ValueError("order_execution.mode='live' requires credential_tier='live'")
    if order_execution_cfg.mode == "live" and not (api_key and api_secret):
        raise ValueError("order_execution.mode='live' requires live API credentials")
    if order_execution_cfg.mode != "live":
        return None
    return CCXTOrderExecutionAdapter(
        exchange_id=execution_cfg.exchange,
        api_key=api_key,
        api_secret=api_secret,
    )


def _log_startup(pipeline_cfg: PipelineConfig, risk_cfg: RiskConfig) -> None:
    execution_cfg = pipeline_cfg.execution
    logger.info("═══════════════════════════════════════════════════════════")
    logger.info(f"  Trader Engine Starting [{pipeline_cfg.timeframe}]")
    logger.info(
        f"  Sync: {execution_cfg.sync_to_boundary} | "
        f"Heartbeat: {execution_cfg.heartbeat_seconds}s"
    )
    logger.info(
        f"  Risk: {risk_cfg.name} | "
        f"Cluster Cap: {risk_cfg.max_cluster_exposure:.2%} | "
        f"Max Leverage: {risk_cfg.max_leverage:.2f}x"
    )
    logger.info("═══════════════════════════════════════════════════════════")


async def _run_boot_reconciliation(
    state: TradeStateManager,
    snapshot_provider: ExchangeSnapshotProvider | None,
    api_key: str,
    api_secret: str,
    notifier: TelegramNotifier,
) -> None:
    run_id = await run_boot_reconciliation(
        state=state,
        snapshot_provider=snapshot_provider,
        credentials_available=bool(api_key and api_secret),
    )
    run = next(item for item in state.get_reconciliation_runs() if item["id"] == run_id)
    delta_count = len(state.get_reconciliation_deltas(run_id=run_id))
    if run["status"] == "MATCHED":
        return
    logger.warning(
        f"Boot reconciliation status={run['status']} deltas={delta_count}. No actions taken."
    )
    await notifier.send(
        f"⚠️ <b>Boot Reconciliation:</b> {run['status']}\n"
        f"Deltas: {delta_count}\n"
        "Mode: read-only, no actions taken."
    )


async def _run_ticks(
    trader: Any,
    state: TradeStateManager,
    pairs: list[dict[str, Any]],
    pipeline_cfg: PipelineConfig,
    strategy_cfg: StrategyConfig,
    notifier: TelegramNotifier,
    api_key: str,
    api_secret: str,
    order_adapter,
) -> None:
    open_pos = state.get_open_positions()
    if open_pos:
        logger.info(f"Resuming with {len(open_pos)} open positions.")

    tick_count = 0
    while True:
        await _sleep_until_next_tick(trader, state, pairs, pipeline_cfg, notifier, api_key, api_secret)
        await trader.execute_tick(
            pairs,
            state,
            notifier,
            pipeline_cfg.timeframe,
            strategy_cfg.model_dump(),
            exchange_id=pipeline_cfg.execution.exchange,
            api_key=api_key,
            api_secret=api_secret,
            order_execution_cfg=pipeline_cfg.execution.order_execution,
            order_execution_adapter=order_adapter,
        )
        tick_count += 1
        if pipeline_cfg.execution.max_ticks is not None and tick_count >= pipeline_cfg.execution.max_ticks:
            logger.info(f"Completed {pipeline_cfg.execution.max_ticks} ticks. Auto-stopping.")
            break


async def _sleep_until_next_tick(
    trader: Any,
    state: TradeStateManager,
    pairs: list[dict[str, Any]],
    pipeline_cfg: PipelineConfig,
    notifier: TelegramNotifier,
    api_key: str,
    api_secret: str,
) -> None:
    execution_cfg = pipeline_cfg.execution
    sleep_seconds = (
        trader.seconds_until_next_candle(pipeline_cfg.timeframe)
        if execution_cfg.sync_to_boundary
        else execution_cfg.heartbeat_seconds
    )
    target_time = datetime.now(timezone.utc) + timedelta(seconds=sleep_seconds)
    logger.info(f"Next tick scheduled for {target_time:%Y-%m-%d %H:%M:%S} UTC.")
    while True:
        await trader.process_user_commands(
            state,
            pairs,
            notifier,
            pipeline_cfg.timeframe,
            exchange_id=execution_cfg.exchange,
            api_key=api_key,
            api_secret=api_secret,
        )
        now = datetime.now(timezone.utc)
        if now >= target_time:
            return
        await asyncio.sleep(min(10.0, (target_time - now).total_seconds()))
