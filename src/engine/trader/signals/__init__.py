"""Signal evaluation package for the trader engine."""

from src.engine.trader.signals.evaluator import evaluate_signal
from src.engine.trader.signals.models import SignalResult

__all__ = ["SignalResult", "evaluate_signal"]
