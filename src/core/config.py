import os
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

    # API Keys are mandatory if in production
    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None

    # Discord/Telegram Webhooks natively here
    webhook_url: Optional[str] = None


# Instantiated globally for injection elsewhere
settings = Settings()
