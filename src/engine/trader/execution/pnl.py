"""PnL helper calculations for trader execution."""

from typing import Any

from src.engine.trader.state_manager import TradeStateManager


def calculate_unrealized_pnl(
    state: TradeStateManager,
    pair_prices: dict[str, tuple[float, float]],
) -> float:
    """Calculate total unrealized PnL across open positions."""
    open_positions = state.get_open_positions()
    total_unrealized = 0.0

    for pos in open_positions:
        label = pos["pair_label"]
        if label not in pair_prices:
            continue

        current_a, current_b = pair_prices[label]
        unrealized = _calculate_position_pnl(pos, current_a, current_b)
        total_unrealized += unrealized

    return total_unrealized


def calculate_per_pair_pnl(
    state: TradeStateManager,
    pair_prices: dict[str, tuple[float, float]],
) -> dict[str, float]:
    """Calculate unrealized PnL by pair for open positions."""
    open_positions = state.get_open_positions()
    per_pair = {}

    for pos in open_positions:
        label = pos["pair_label"]
        if label not in pair_prices:
            continue

        current_a, current_b = pair_prices[label]
        per_pair[label] = _calculate_position_pnl(pos, current_a, current_b)

    return per_pair


def _calculate_position_pnl(
    position: dict[str, Any],
    current_a: float,
    current_b: float,
) -> float:
    ret_a = (current_a - position["entry_price_a"]) / position["entry_price_a"]
    ret_b = (current_b - position["entry_price_b"]) / position["entry_price_b"]

    if position["side"] == "LONG_SPREAD":
        return position["weight_a"] * ret_a - position["weight_b"] * ret_b
    return -position["weight_a"] * ret_a + position["weight_b"] * ret_b
