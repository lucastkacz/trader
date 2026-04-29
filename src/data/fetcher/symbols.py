"""Symbol normalization helpers for CCXT market access."""


def to_display_symbol(symbol: str) -> str:
    """Return the strategy/display symbol without a derivative settlement suffix."""
    return symbol.split(":", maxsplit=1)[0]


def to_ccxt_linear_swap_symbol(symbol: str) -> str:
    """Return CCXT's base/quote:settlement symbol for linear swap contracts."""
    if ":" in symbol:
        return symbol
    quote_currency = symbol.split("/")[-1]
    return f"{symbol}:{quote_currency}"
