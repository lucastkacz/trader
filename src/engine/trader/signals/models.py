"""Signal models for the trader engine."""

from dataclasses import dataclass


@dataclass
class SignalResult:
    """Immutable output of a single signal evaluation."""

    signal: str          # LONG_SPREAD | SHORT_SPREAD | FLAT
    z_score: float       # Current Z-Score value
    weight_a: float      # Volatility parity weight for Asset A
    weight_b: float      # Volatility parity weight for Asset B
    spread: float        # Current raw spread value
    price_a: float       # Latest close of Asset A
    price_b: float       # Latest close of Asset B
