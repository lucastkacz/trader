"""Configured runtime context for the Telegram operator daemon."""

from pathlib import Path
from typing import Optional

from src.engine.trader.config import TelegramConfig
from src.engine.trader.config import load_telegram_config as load_typed_telegram_config
from src.engine.trader.state_manager import TradeStateManager

TELEGRAM_DB_PATH: Optional[str] = None
TELEGRAM_ENVIRONMENT: Optional[str] = None
TELEGRAM_HOLDING_PERIOD_BAR_MINUTES: Optional[float] = None
TELEGRAM_PROMOTED_PAIRS_PATH: Optional[str] = None
TELEGRAM_HEALTH_STALE_AFTER_MINUTES: Optional[float] = None


def configure_daemon(config_path: str) -> TelegramConfig:
    """Configure daemon process globals from typed YAML config."""
    global TELEGRAM_DB_PATH, TELEGRAM_ENVIRONMENT, TELEGRAM_HOLDING_PERIOD_BAR_MINUTES
    global TELEGRAM_PROMOTED_PAIRS_PATH, TELEGRAM_HEALTH_STALE_AFTER_MINUTES
    cfg = load_typed_telegram_config(config_path)
    TELEGRAM_DB_PATH = cfg.db_path
    TELEGRAM_ENVIRONMENT = cfg.environment
    TELEGRAM_HOLDING_PERIOD_BAR_MINUTES = cfg.holding_period_bar_minutes
    TELEGRAM_PROMOTED_PAIRS_PATH = cfg.promoted_pairs_path
    TELEGRAM_HEALTH_STALE_AFTER_MINUTES = cfg.health_stale_after_minutes
    return cfg


def reset_daemon_context() -> None:
    """Reset process globals for tests."""
    global TELEGRAM_DB_PATH, TELEGRAM_ENVIRONMENT, TELEGRAM_HOLDING_PERIOD_BAR_MINUTES
    global TELEGRAM_PROMOTED_PAIRS_PATH, TELEGRAM_HEALTH_STALE_AFTER_MINUTES
    TELEGRAM_DB_PATH = None
    TELEGRAM_ENVIRONMENT = None
    TELEGRAM_HOLDING_PERIOD_BAR_MINUTES = None
    TELEGRAM_PROMOTED_PAIRS_PATH = None
    TELEGRAM_HEALTH_STALE_AFTER_MINUTES = None


def open_state_manager() -> TradeStateManager:
    """Open a short-lived state connection for one command handler."""
    if TELEGRAM_DB_PATH is None:
        raise RuntimeError("Telegram daemon db_path is not configured")
    return TradeStateManager(db_path=TELEGRAM_DB_PATH)


def environment_label() -> str | None:
    return TELEGRAM_ENVIRONMENT


def holding_period_bar_minutes() -> float:
    if TELEGRAM_HOLDING_PERIOD_BAR_MINUTES is None:
        raise RuntimeError("Telegram daemon holding_period_bar_minutes is not configured")
    return TELEGRAM_HOLDING_PERIOD_BAR_MINUTES


def promoted_pairs_path() -> Path:
    if TELEGRAM_PROMOTED_PAIRS_PATH is None:
        raise RuntimeError("Telegram daemon promoted_pairs_path is not configured")
    return Path(TELEGRAM_PROMOTED_PAIRS_PATH)


def health_stale_after_minutes() -> float:
    if TELEGRAM_HEALTH_STALE_AFTER_MINUTES is None:
        raise RuntimeError("Telegram daemon health_stale_after_minutes is not configured")
    return TELEGRAM_HEALTH_STALE_AFTER_MINUTES
