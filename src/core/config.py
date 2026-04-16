from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """
    Core Configuration Settings.
    Secret credentials are read strictly from the .env file.
    Hyperparameters can safely reside here.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Base settings
    env: str = Field(default="production", description="Environment: dev, test, production")

    # API Keys (Binance — used for historical data mining in Epoch 1)
    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None

    # API Keys (Bybit — used for live ghost trading in Epoch 3+)
    bybit_readonly_api_key: Optional[str] = None
    bybit_readonly_api_secret: Optional[str] = None

    # Ghost Trader (Epoch 3)
    ghost_exchange: str = Field(default="bybit", description="Exchange for live price feeds: 'bybit' or 'binance'")
    ghost_db_path: str = Field(default="data/ghost/trades.db", description="SQLite path for ghost trading state")
    ghost_min_sharpe: float = Field(default=1.0, description="Minimum Sharpe ratio cutoff for Tier 1 pairs")

    # Discord/Telegram Webhooks natively here
    webhook_url: Optional[str] = None
    telegram_bot_token: Optional[str] = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(default=None, alias="TELEGRAM_CHAT_ID")


# Instantiated globally for injection elsewhere
settings = Settings()
