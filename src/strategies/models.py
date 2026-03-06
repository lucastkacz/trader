from pydantic import BaseModel, ConfigDict
from typing import Optional
from src.strategies.constants import MeanReversionMethod

class MethodologyConfig(BaseModel):
    """Configuration schema for strategy methodology using strictly typed Enums."""
    mean_reversion_detection: MeanReversionMethod
    signal_generation: Optional[str] = None
    relationship_type: Optional[str] = None
    
    # Allow other methodology descriptors if needed
    model_config = ConfigDict(extra='allow')

class StrategyParameters(BaseModel):
    """Schema for strategy parameters, requiring methodology block."""
    methodology: MethodologyConfig
    
    # Allow arbitrary parameter fields (like cointegration_window, etc.)
    model_config = ConfigDict(extra='allow')

class StrategyConfig(BaseModel):
    """Root configuration schema for any strategy loaded from YAML."""
    name: str
    description: Optional[str] = None
    author: Optional[str] = None
    version: Optional[str] = None
    timeframe: Optional[str] = "1h"
    parameters: StrategyParameters
    
    model_config = ConfigDict(extra='allow')
