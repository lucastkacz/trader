"""Report data models."""

from dataclasses import asdict, dataclass
from typing import Any, Optional


@dataclass
class PairMetrics:
    """Per-pair performance breakdown."""

    pair_label: str
    asset_x: str
    asset_y: str
    realized_pnl: float
    unrealized_pnl: float
    trade_count: int
    win_rate: float
    avg_pnl_per_trade: float
    avg_holding_bars: float
    current_status: str
    current_z_score: Optional[float]
    backtest_sharpe: Optional[float]
    backtest_pnl: Optional[float]
    live_vs_backtest: str


@dataclass
class SignalQuality:
    """Signal predictive accuracy metrics."""

    signal_accuracy: float
    avg_entry_z: float
    avg_exit_z: Optional[float]
    false_signal_rate: float
    total_signals_recorded: int


@dataclass
class RiskSnapshot:
    """Current risk state of the portfolio."""

    portfolio_heat: float
    largest_single_loss: float
    days_since_last_trade: float
    consecutive_losses: int
    data_freshness: str


@dataclass
class StateLedgerSnapshot:
    """Current ledger/audit state counts for operator reporting."""

    total_order_events: int
    leg_targets_by_status_role: dict[str, dict[str, int]]
    user_commands_by_status: dict[str, int]
    latest_reconciliation_run_status: Optional[str]
    reconciliation_delta_count: int


@dataclass
class TradeReport:
    """Complete report output."""

    total_equity_pct: float
    realized_pnl_pct: float
    unrealized_pnl_pct: float
    active_pairs: int
    total_trades: int
    uptime_hours: float
    status: str

    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    max_drawdown_pct: float
    calmar_ratio: Optional[float]
    win_rate: float
    profit_factor: Optional[float]
    expectancy: float
    avg_holding_bars: float
    trades_per_week: float

    per_pair: list[PairMetrics]
    signal_quality: SignalQuality
    risk: RiskSnapshot
    state_ledger: StateLedgerSnapshot

    backtest_avg_sharpe: Optional[float]
    backtest_avg_pnl: Optional[float]

    trade_log: list[dict[str, Any]]
    equity_curve: list[dict[str, Any]]

    report_timestamp: str
    db_path: str
    bars_per_year: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dictionary."""
        return asdict(self)
