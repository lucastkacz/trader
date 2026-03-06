from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any, Tuple

from src.strategies.models import StrategyConfig

class BaseStrategy(ABC):
    """
    Abstract Base Class for all trading strategies in the Strategy Lab.
    Enforces a strict contract: every strategy must define how to process
    historical data and return a set of target weights for the Engine.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the strategy with a configuration dictionary.
        
        Args:
            config: A dictionary loaded from the strategy's config.yml file.
        """
        self.raw_config = config
        try:
            # Strictly validate the YAML-parsed config using Pydantic
            self.validated_config = StrategyConfig(**config)
        except Exception as e:
            raise ValueError(f"Strategy Configuration Validation Error: {e}")
            
    @property
    def config(self) -> Dict[str, Any]:
        """Provides backward-compatibility for direct config dictionary access."""
        return self.raw_config
        
    @property
    def methodology(self) -> str:
        """
        Returns the standardized Mean Reversion Method (e.g., from MeanReversionMethod Enum)
        defined in the strategy's config.yml, safely typed by Pydantic.
        """
        return self.validated_config.parameters.methodology.mean_reversion_detection.value
        
    @abstractmethod
    def evaluate(self, prices: pd.DataFrame, asset_a: str, asset_b: str = None) -> Dict[str, Any]:
        """
        Core evaluation method. Processes data and generates target weights for the Execution Engine.
        
        Args:
            prices: A DataFrame of historical prices (columns are tickers, index is datetime).
            asset_a: The primary asset (or base asset of a pair).
            asset_b: The secondary asset (optional, for pairs/spread strategies).
            
        Returns:
            A dictionary containing the results. At a minimum, it should include:
            - 'status': 'Success' or an error message.
            - 'weights': A DataFrame of target weights matching the original prices DataFrame.
            - Other useful metrics specific to the strategy.
        """
        pass

    @abstractmethod
    def get_screening_metric(self, prices: pd.DataFrame, asset_a: str, asset_b: str = None) -> Tuple[float, Dict[str, Any]]:
        """
        Returns a primary metric for screening (e.g. p-value) and a dict of additional metadata (e.g. hedge_ratio).
        Lower is usually better by default, unless sort_ascending returns False.
        If the pair does not meet minimum valid thresholds, return (None, {}).
        """
        pass
        
    @property
    @abstractmethod
    def sort_ascending(self) -> bool:
        """
        Returns True if a lower screening metric is better (e.g., P-Value). 
        Returns False if a higher screening metric is better (e.g., Correlation, Sharpe).
        """
        pass
