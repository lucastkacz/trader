"""Trader runtime loop orchestration."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from src.core.config import settings
from src.core.logger import logger
from src.engine.trader.commands.processor import process_user_commands
from src.engine.trader.config import PipelineConfig, RiskConfig, StrategyConfig
from src.engine.trader.execution.orders import CCXTOrderExecutionAdapter
from src.engine.trader.reconciliation import ExchangeSnapshotProvider, run_boot_reconciliation
from src.engine.trader.runtime.monitoring.health import (
    build_trader_health_snapshot,
    render_trader_health_snapshot,
)
from src.engine.trader.runtime.monitoring.run_status import (
    record_observer_max_ticks_completed,
    record_observer_run_failed,
    record_observer_run_interrupted,
    record_observer_run_started,
)
from src.engine.trader.runtime.pair_queue import PairQueuePolicy
from src.engine.trader.runtime.pair_validity import PairValidityConfig, build_pair_validity_report
from src.engine.trader.runtime.pre_trade_risk import pre_trade_policy_from_config
from src.engine.trader.runtime.artifacts import load_tier1_pairs, promoted_pair_artifact_path
from src.engine.trader.runtime.scheduler import seconds_until_next_candle
from src.engine.trader.runtime.tick import execute_tick
from src.engine.trader.state.manager import TradeStateManager
from src.interfaces.telegram.notifier import TelegramNotifier


def resolve_credentials(settings: Any, credential_tier: str) -> tuple[str, str]:
    """Resolve API key/secret from configured credential tier."""
    if credential_tier == "live":
        return settings.exchange_live_api_key or "", settings.exchange_live_api_secret or ""
    return settings.exchange_readonly_api_key or "", settings.exchange_readonly_api_secret or ""


async def run_trader_loop(
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

    notifier = notifier or TelegramNotifier(
        environment=pipeline_cfg.name,
        execution_mode=execution_cfg.order_execution.mode,
    )
    await notifier.send(f"🟢 <b>System Boot:</b> Engine Synchronized on {pipeline_cfg.timeframe}")

    pairs = load_tier1_pairs(
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
        record_observer_run_started(state, max_ticks=execution_cfg.max_ticks)
        await _run_boot_reconciliation(state, reconciliation_snapshot_provider, api_key, api_secret, notifier)
        await _notify_boot_health(state, pipeline_cfg, notifier)
        await _run_ticks(
            state=state,
            pairs=pairs,
            pipeline_cfg=pipeline_cfg,
            strategy_cfg=strategy_cfg,
            risk_cfg=risk_cfg,
            notifier=notifier,
            api_key=api_key,
            api_secret=api_secret,
            order_adapter=order_adapter,
        )
    except asyncio.CancelledError:
        record_observer_run_interrupted(state)
        logger.info("Trader Engine shutdown requested by async cancellation.")
        raise
    except KeyboardInterrupt:
        record_observer_run_interrupted(state)
        logger.info("Trader Engine shut down by user (KeyboardInterrupt).")
    except Exception as exc:
        record_observer_run_failed(state, reason=str(exc))
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
    state: TradeStateManager,
    pairs: list[dict[str, Any]],
    pipeline_cfg: PipelineConfig,
    strategy_cfg: StrategyConfig,
    risk_cfg: RiskConfig,
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
        await _sleep_until_next_tick(state, pairs, pipeline_cfg, notifier, api_key, api_secret)
        pair_queue_enabled = (
            pipeline_cfg.execution.pair_queue.enabled
            and pipeline_cfg.execution.pair_queue.mode == "future_entries"
        )
        pair_validity = (
            build_pair_validity_report(
                surviving_pairs_path=promoted_pair_artifact_path(
                    pipeline_cfg.timeframe,
                    pipeline_cfg.execution.artifact_base_dir,
                ),
                market_data_base_dir=pipeline_cfg.execution.market_data_base_dir,
                state=state,
                config=PairValidityConfig(
                    **pipeline_cfg.execution.pair_validity.to_runtime_config_kwargs()
                ),
            )
            if pair_queue_enabled else None
        )
        await execute_tick(
            pairs,
            state,
            notifier,
            pipeline_cfg.timeframe,
            strategy_cfg,
            exchange_id=pipeline_cfg.execution.exchange,
            api_key=api_key,
            api_secret=api_secret,
            order_execution_cfg=pipeline_cfg.execution.order_execution,
            order_execution_adapter=order_adapter,
            pair_queue_policy=PairQueuePolicy(
                **pipeline_cfg.execution.pair_queue.to_runtime_policy_kwargs()
            ),
            pair_validity_snapshots=(
                pair_validity.snapshots if pair_validity is not None else None
            ),
            pair_queue_enabled=pair_queue_enabled,
            pre_trade_risk_policy=pre_trade_policy_from_config(risk_cfg),
        )
        tick_count += 1
        if pipeline_cfg.execution.max_ticks is not None and tick_count >= pipeline_cfg.execution.max_ticks:
            logger.info(f"Completed {pipeline_cfg.execution.max_ticks} ticks. Auto-stopping.")
            open_positions = state.get_open_positions()
            record_observer_max_ticks_completed(
                state,
                max_ticks=pipeline_cfg.execution.max_ticks,
                completed_ticks=tick_count,
                open_position_ids=[int(position["id"]) for position in open_positions],
            )
            exposure_line = (
                "No exchange exposure exists in state-only mode."
                if pipeline_cfg.execution.order_execution.mode == "state_only"
                else "Review exchange exposure before restart."
            )
            await notifier.send(
                "🛑 <b>Runtime Auto-Stopped</b>\n"
                f"Completed {pipeline_cfg.execution.max_ticks} ticks.\n"
                f"Open local positions remain: {len(open_positions)}.\n"
                f"{exposure_line}\n"
                "Restart observer to continue natural-exit evaluation."
            )
            break


async def _notify_boot_health(
    state: TradeStateManager,
    pipeline_cfg: PipelineConfig,
    notifier: TelegramNotifier,
) -> None:
    stale_after_minutes = max(1.0, pipeline_cfg.execution.heartbeat_seconds * 2.0 / 60.0)
    snapshot = build_trader_health_snapshot(
        state,
        environment=pipeline_cfg.name,
        stale_after_minutes=stale_after_minutes,
    )
    if snapshot.open_positions == 0 and snapshot.status == "HEALTHY":
        return
    await notifier.send(
        render_trader_health_snapshot(snapshot, title="BOOT HEALTH")
    )


async def _sleep_until_next_tick(
    state: TradeStateManager,
    pairs: list[dict[str, Any]],
    pipeline_cfg: PipelineConfig,
    notifier: TelegramNotifier,
    api_key: str,
    api_secret: str,
) -> None:
    execution_cfg = pipeline_cfg.execution
    sleep_seconds = (
        seconds_until_next_candle(pipeline_cfg.timeframe)
        if execution_cfg.sync_to_boundary
        else execution_cfg.heartbeat_seconds
    )
    target_time = datetime.now(timezone.utc) + timedelta(seconds=sleep_seconds)
    logger.info(f"Next tick scheduled for {target_time:%Y-%m-%d %H:%M:%S} UTC.")
    while True:
        await process_user_commands(
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
