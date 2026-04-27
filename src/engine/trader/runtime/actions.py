"""Trader action decision helpers."""


def determine_action(current_side: str | None, new_signal: str) -> str:
    """Determine state-transition action from current side and new signal."""
    if current_side is None:
        if new_signal == "FLAT":
            return "SKIP"
        return "ENTRY"

    if new_signal == "FLAT":
        return "EXIT"
    if new_signal == current_side:
        return "HOLD"
    return "FLIP"
