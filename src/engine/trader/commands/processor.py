"""Trader-side user command processor."""

from typing import Any

from src.core.logger import logger
from src.engine.trader.execution.liquidation import execute_emergency_liquidation
from src.engine.trader.state_manager import TradeStateManager
from src.interfaces.telegram.notifier import TelegramNotifier


async def process_user_commands(
    state: TradeStateManager,
    pairs: list[dict[str, Any]],
    notifier: TelegramNotifier,
    timeframe: str,
    exchange_id: str,
    api_key: str,
    api_secret: str,
) -> None:
    """Claim and execute all pending UI commands."""
    commands = state.claim_pending_commands()
    for cmd in commands:
        command_id = cmd["id"]
        action = cmd["command"]
        target = cmd["target_pair"]
        logger.info(f"Processing UI Command: {action} on {target}")

        try:
            if action == "/stop_all":
                await execute_emergency_liquidation(
                    state,
                    pairs,
                    notifier,
                    timeframe,
                    exchange_id=exchange_id,
                    api_key=api_key,
                    api_secret=api_secret,
                    target=None,
                )
            elif action == "/stop":
                await execute_emergency_liquidation(
                    state,
                    pairs,
                    notifier,
                    timeframe,
                    exchange_id=exchange_id,
                    api_key=api_key,
                    api_secret=api_secret,
                    target=target,
                )
            elif action == "/pause":
                state.set_system_paused(True)
                if notifier:
                    await notifier.send("⏸️ <b>SYSTEM PAUSED</b>\nNo new trades will be executed.")
            elif action == "/resume":
                state.set_system_paused(False)
                if notifier:
                    await notifier.send("▶️ <b>SYSTEM RESUMED</b>\nTick execution restored.")
            else:
                logger.warning(f"Unknown command {action}")
                state.mark_command_ignored(command_id, "unknown command")
                continue
            state.mark_command_executed(command_id)
        except Exception as exc:
            state.mark_command_failed(command_id, str(exc))
            logger.error(f"Failed executing command {action}: {exc}")
            if notifier:
                await notifier.send(f"⚠️ COMMAND FAILED: {action} ({exc})")
