from src.data.fetcher.symbols import (
    to_ccxt_linear_swap_symbol,
    to_display_symbol,
)


def test_to_ccxt_linear_swap_symbol_adds_settlement_suffix():
    assert to_ccxt_linear_swap_symbol("BTC/USDT") == "BTC/USDT:USDT"


def test_to_ccxt_linear_swap_symbol_preserves_resolved_ccxt_symbol():
    assert to_ccxt_linear_swap_symbol("BTC/USDT:USDT") == "BTC/USDT:USDT"


def test_to_display_symbol_strips_settlement_suffix():
    assert to_display_symbol("BTC/USDT:USDT") == "BTC/USDT"


def test_to_display_symbol_preserves_display_symbol():
    assert to_display_symbol("BTC/USDT") == "BTC/USDT"
