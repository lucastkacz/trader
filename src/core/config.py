from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """
    Core Secrets Configuration.
    Read strictly from the .env file via pydantic-settings.
    Contains ONLY credentials and behavior toggles — zero hyperparameters.
    Hyperparameters belong exclusively in configs/pipelines/*.yml.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Controls Loguru dual-sink behavior (see PLAN/10_environment_and_secrets_strategy.md)
    # debug  = verbose console + JSON sink (local development)
    # info   = quiet console + JSON sink (VPS deployment)
    # silent = JSON sink only, no console (pytest Airplane Mode)
    log_level: Literal["debug", "info", "silent"] = Field(
        default="info",
        description="Logger verbosity mode: debug | info | silent"
    )

    # Exchange credentials — exchange-agnostic slots.
    # The exchange adapter (bybit, kucoin, etc.) is declared in pipeline YAML.
    # Read-Only key: used by DEV (local) and UAT (VPS paper trading).
    exchange_readonly_api_key: Optional[str] = None
    exchange_readonly_api_secret: Optional[str] = None

    # Live-Trading key: used by PROD only. Must be empty in all other environments.
    exchange_live_api_key: Optional[str] = None
    exchange_live_api_secret: Optional[str] = None

    # Telegram notification credentials
    telegram_bot_token: Optional[str] = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(default=None, alias="TELEGRAM_CHAT_ID")


# Instantiated globally for injection elsewhere
settings = Settings()
