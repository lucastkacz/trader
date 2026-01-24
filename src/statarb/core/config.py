import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings

class MarketDataConfig(BaseModel):
    exchanges: list[str]
    timeframes: list[str]

class RiskConfig(BaseModel):
    max_drawdown_pct: float
    allowed_leverage: float

class PathsConfig(BaseModel):
    data_dir: str
    lake_dir: str
    db_path: str
    logs_dir: str

class ExecutionConfig(BaseModel):
    mode: str
    paper_balance: float = 0.0

class AppConfig(BaseSettings):
    environment: Literal["local", "paper", "live"] = "local"
    paths: PathsConfig
    market_data: MarketDataConfig
    risk: RiskConfig
    execution: ExecutionConfig
    live_execution_enabled: bool = False

    @classmethod
    def load(cls, env: str = "local") -> "AppConfig":
        config_path = Path(f"config/environments/{env}.yaml")
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
            
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
            
        return cls(**data)
