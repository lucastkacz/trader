"""Single-tick orchestration for the trader runtime."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

from src.core.logger import logger
from src.engine.trader.config import OrderExecutionConfig, StrategyConfig
from src.engine.trader.execution.market_data import (
    ReadonlyMarketDataFetchPolicy,
    fetch_recent_candles,
)
from src.engine.trader.execution.orders import OrderExecutionAdapter
from src.engine.trader.execution.pnl import calculate_per_pair_pnl, calculate_unrealized_pnl
from src.engine.trader.runtime.pair_queue import PairQueuePolicy
from src.engine.trader.runtime.pair_queue.execution import (
    allow_new_entry_from_queue,
    build_queue_decisions_for_tick,
    order_evaluations_for_transition,
)
from src.engine.trader.runtime.pair_validity.models import PairValiditySnapshot
from src.engine.trader.runtime.risk import (
    PreTradeLiquiditySnapshot,
    PreTradeRiskPolicy,
    liquidity_snapshot_from_candles,
)
from src.engine.trader.runtime.signal_transition import (
    determine_action,
    route_signal_transition,
)
from src.engine.trader.signals.evaluator import evaluate_signal
from src.engine.trader.state.manager import TradeStateManager
from src.interfaces.telegram.notifier import TelegramNotifier


@dataclass(frozen=True)
class PairTickEvaluation:
    pair: dict[str, Any]
    pair_label: str
    current_side: str | None
    lookback_bars: int
    result: Any
    action: str
    liquidity_snapshot: PreTradeLiquiditySnapshot | None


async def execute_tick(
    pairs: list[dict[str, Any]],
    state: TradeStateManager,
    notifier: TelegramNotifier,
    timeframe: str,
    strategy_cfg: StrategyConfig,
    exchange_id: str,
    api_key: str,
    api_secret: str,
    order_execution_cfg: OrderExecutionConfig,
    order_execution_adapter: OrderExecutionAdapter | None,
    market_data_fetch_policy: ReadonlyMarketDataFetchPolicy | None = None,
    pair_queue_policy: PairQueuePolicy | None = None,
    pair_validity_snapshots: Sequence[PairValiditySnapshot] | None = None,
    pair_queue_enabled: bool = False,
    pre_trade_risk_policy: PreTradeRiskPolicy | None = None,
) -> None:
    """Execute one full trader tick across all configured pairs."""
    if state.is_system_paused():
        logger.info("Tick skipped because system is paused.")
        return

    logger.info(f"═══ ENGINE TICK @ {datetime.now(timezone.utc).isoformat()} ═══")
    pair_prices = {}
    evaluations = []
    candle_cache = {}
    for pair in pairs:
        evaluation = await _evaluate_pair_tick(
            pair=pair,
            pair_prices=pair_prices,
            state=state,
            timeframe=timeframe,
            strategy_cfg=strategy_cfg,
            exchange_id=exchange_id,
            api_key=api_key,
            api_secret=api_secret,
            market_data_fetch_policy=market_data_fetch_policy,
            candle_cache=candle_cache,
            pre_trade_risk_policy=pre_trade_risk_policy,
        )
        if evaluation is not None:
            evaluations.append(evaluation)

    queue_decisions = build_queue_decisions_for_tick(
        evaluations=evaluations,
        open_positions=state.get_open_positions(),
        policy=pair_queue_policy,
        validity_snapshots=pair_validity_snapshots,
        enabled=pair_queue_enabled,
    )

    ordered_evaluations = order_evaluations_for_transition(evaluations, queue_decisions)
    for evaluation in ordered_evaluations:
        if pair_queue_enabled:
            queue_decisions = build_queue_decisions_for_tick(
                evaluations=evaluations,
                open_positions=state.get_open_positions(),
                policy=pair_queue_policy,
                validity_snapshots=pair_validity_snapshots,
                enabled=pair_queue_enabled,
            )
        decision = queue_decisions.get(evaluation.pair_label)
        allow_new_entry = allow_new_entry_from_queue(
            evaluation,
            decision,
            pair_queue_enabled,
        )
        await route_signal_transition(
            pair=evaluation.pair,
            pair_label=evaluation.pair_label,
            current_side=evaluation.current_side,
            result=evaluation.result,
            lookback_bars=evaluation.lookback_bars,
            timeframe=timeframe,
            state=state,
            notifier=notifier,
            order_execution_cfg=order_execution_cfg,
            order_execution_adapter=order_execution_adapter,
            allow_new_entry=allow_new_entry,
            entry_block_reasons=decision.block_reasons if decision is not None else None,
            pre_trade_risk_policy=pre_trade_risk_policy,
            pre_trade_liquidity_snapshot=evaluation.liquidity_snapshot,
        )
    _snapshot_tick_equity(state, pair_prices)


async def _evaluate_pair_tick(
    pair: dict[str, Any],
    pair_prices: dict[str, tuple[float, float]],
    state: TradeStateManager,
    timeframe: str,
    strategy_cfg: StrategyConfig,
    exchange_id: str,
    api_key: str,
    api_secret: str,
    market_data_fetch_policy: ReadonlyMarketDataFetchPolicy | None,
    candle_cache: dict[str, tuple[int, Any]],
    pre_trade_risk_policy: PreTradeRiskPolicy | None,
) -> PairTickEvaluation | None:
    pair_label = f"{pair['Asset_X']}|{pair['Asset_Y']}"
    df_a, df_b = await _fetch_pair_candles(
        pair,
        timeframe,
        exchange_id,
        api_key,
        api_secret,
        market_data_fetch_policy=market_data_fetch_policy,
        candle_cache=candle_cache,
    )
    if df_a is None or df_b is None:
        return None
    liquidity_snapshot = (
        liquidity_snapshot_from_candles(
            df_a,
            df_b,
            lookback_bars=pre_trade_risk_policy.liquidity_lookback_bars,
        )
        if pre_trade_risk_policy is not None
        else None
    )

    current_pos = state.get_position_for_pair(pair_label)
    current_side = current_pos["side"] if current_pos else None
    best_params = pair["Best_Params"]
    result = evaluate_signal(
        df_a=df_a,
        df_b=df_b,
        entry_z=best_params["entry_z"],
        exit_z=strategy_cfg.execution.exit_z_score,
        lookback_bars=best_params["lookback_bars"],
        vol_lookback_bars=strategy_cfg.execution.volatility_lookback_bars,
        hedge_ratio=pair["Hedge_Ratio"],
        current_side=current_side,
    )
    pair_prices[pair_label] = (result.price_a, result.price_b)
    action = determine_action(current_side, result.signal)
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
    return PairTickEvaluation(
        pair=pair,
        pair_label=pair_label,
        current_side=current_side,
        lookback_bars=best_params["lookback_bars"],
        result=result,
        action=action,
        liquidity_snapshot=liquidity_snapshot,
    )


async def _fetch_pair_candles(
    pair: dict[str, Any],
    timeframe: str,
    exchange_id: str,
    api_key: str,
    api_secret: str,
    *,
    market_data_fetch_policy: ReadonlyMarketDataFetchPolicy | None,
    candle_cache: dict[str, tuple[int, Any]],
) -> tuple[Any | None, Any | None]:
    bars_needed = pair["Best_Params"]["lookback_bars"] + 50
    try:
        df_a = await _fetch_symbol_candles(
            symbol=pair["Asset_X"],
            bars_needed=bars_needed,
            timeframe=timeframe,
            exchange_id=exchange_id,
            api_key=api_key,
            api_secret=api_secret,
            policy=market_data_fetch_policy,
            candle_cache=candle_cache,
        )
        df_b = await _fetch_symbol_candles(
            symbol=pair["Asset_Y"],
            bars_needed=bars_needed,
            timeframe=timeframe,
            exchange_id=exchange_id,
            api_key=api_key,
            api_secret=api_secret,
            policy=market_data_fetch_policy,
            candle_cache=candle_cache,
        )
    except Exception as exc:
        logger.warning(f"Failed fetching data for {pair['Asset_X']}|{pair['Asset_Y']}: {exc}")
        return None, None
    return df_a, df_b


async def _fetch_symbol_candles(
    *,
    symbol: str,
    bars_needed: int,
    timeframe: str,
    exchange_id: str,
    api_key: str,
    api_secret: str,
    policy: ReadonlyMarketDataFetchPolicy | None,
    candle_cache: dict[str, tuple[int, Any]],
) -> Any:
    cached = candle_cache.get(symbol)
    if cached is not None and cached[0] >= bars_needed:
        return cached[1]
    if policy is None:
        raise ValueError("Readonly market-data fetch policy is required for runtime OHLCV reads")
    candles = await fetch_recent_candles(
        symbol,
        bars_needed,
        timeframe,
        exchange_id=exchange_id,
        api_key=api_key,
        api_secret=api_secret,
        policy=policy,
    )
    candle_cache[symbol] = (bars_needed, candles)
    return candles


def _snapshot_tick_equity(
    state: TradeStateManager,
    pair_prices: dict[str, tuple[float, float]],
) -> None:
    per_pair_pnl = calculate_per_pair_pnl(state, pair_prices)
    closed = state.get_all_closed()
    realized = sum(trade["realized_pnl_pct"] or 0.0 for trade in closed)
    unrealized = calculate_unrealized_pnl(state, pair_prices)
    open_count = len(state.get_open_positions())
    state.snapshot_equity(
        total_equity_pct=realized + unrealized,
        open_positions=open_count,
        realized_pnl_pct=realized,
        unrealized_pnl_pct=unrealized,
        per_pair_pnl=json.dumps(per_pair_pnl) if per_pair_pnl else None,
    )
    logger.info(
        f"Tick complete | Open: {open_count} | "
        f"Realized: {realized*100:.4f}% | Unrealized: {unrealized*100:.4f}% | "
        f"Total Equity: {(realized+unrealized)*100:.4f}%"
    )
