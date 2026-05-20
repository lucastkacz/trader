"""Live trader runtime orchestration."""

from pathlib import Path
from typing import Any

from src.engine.trader.commands.processor import process_user_commands
from src.engine.trader.config import OrderExecutionConfig, PipelineConfig, RiskConfig, StrategyConfig
from src.engine.trader.execution.liquidation import execute_emergency_liquidation
from src.engine.trader.execution.orders import OrderExecutionAdapter
from src.engine.trader.reconciliation import (
    ExchangeSnapshotProvider,
    ReconciliationAuditReport,
    run_read_only_audit,
)
from src.engine.trader.runtime.pairs import load_tier1_pairs
from src.engine.trader.runtime.scheduler import seconds_until_next_candle
from src.engine.trader.runtime.tick import execute_tick
from src.engine.trader.runtime.trader_runner import run_trader_loop
from src.engine.trader.state.manager import TradeStateManager
from src.interfaces.telegram.notifier import TelegramNotifier


class LiveTrader:
    """High-level trader runtime orchestrator."""

    def load_tier1_pairs(
        self,
        timeframe: str,
        min_sharpe: float,
        exchange: str,
        artifact_base_dir: str | Path,
    ) -> list[dict[str, Any]]:
        return load_tier1_pairs(timeframe, min_sharpe, exchange, artifact_base_dir)

    def seconds_until_next_candle(self, timeframe: str) -> float:
        return seconds_until_next_candle(timeframe)

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
        await run_trader_loop(
            trader=self,
            pipeline_cfg=pipeline_cfg,
            strategy_cfg=strategy_cfg,
            risk_cfg=risk_cfg,
            reconciliation_snapshot_provider=reconciliation_snapshot_provider,
            notifier=notifier,
        )
