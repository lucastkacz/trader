"""Reporting package for trader state."""

from src.engine.trader.reporting.assembler import generate_report
from src.engine.trader.reporting.models import (
    PairMetrics,
    RiskSnapshot,
    SignalQuality,
    StateLedgerSnapshot,
    TradeReport,
)

__all__ = [
    "PairMetrics",
    "RiskSnapshot",
    "SignalQuality",
    "StateLedgerSnapshot",
    "TradeReport",
    "generate_report",
]
