"""Import-compatible facade for trader report computation."""

from src.engine.trader.reporting.assembler import generate_report
from src.engine.trader.reporting.metrics import (
    _compute_calmar,
    _compute_max_drawdown,
    _compute_returns,
    _compute_sharpe,
    _compute_sortino,
    _compute_trade_stats,
    _compute_trades_per_week,
    _compute_uptime_hours,
    _detect_bars_per_year,
    _determine_status,
)
from src.engine.trader.reporting.models import (
    PairMetrics,
    RiskSnapshot,
    SignalQuality,
    StateLedgerSnapshot,
    TradeReport,
)
from src.engine.trader.reporting.per_pair import _compute_per_pair
from src.engine.trader.reporting.risk import _compute_risk
from src.engine.trader.reporting.signal_quality import _compute_signal_quality
from src.engine.trader.reporting.state_ledger import _compute_state_ledger

__all__ = [
    "PairMetrics",
    "RiskSnapshot",
    "SignalQuality",
    "StateLedgerSnapshot",
    "TradeReport",
    "_compute_calmar",
    "_compute_max_drawdown",
    "_compute_per_pair",
    "_compute_returns",
    "_compute_risk",
    "_compute_sharpe",
    "_compute_signal_quality",
    "_compute_sortino",
    "_compute_state_ledger",
    "_compute_trade_stats",
    "_compute_trades_per_week",
    "_compute_uptime_hours",
    "_detect_bars_per_year",
    "_determine_status",
    "generate_report",
]
