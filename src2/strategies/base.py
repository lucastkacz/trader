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

    @abstractmethod
    def render_parameters(self, st) -> Dict[str, Any]:
        """
        Render strategy-specific Streamlit parameter widgets.
        Reads defaults from the strategy's config.yml and creates interactive
        inputs for the user to adjust.
        
        Args:
            st: The Streamlit module (passed to avoid module-level import).
            
        Returns:
            A dict of user-chosen parameter values ready for the pipeline.
        """
        pass

    @abstractmethod
    def render_pipeline(self, st, df_pair: pd.DataFrame, asset_a: str, asset_b: str, params: Dict[str, Any]) -> None:
        """
        Render the full visual inspection pipeline (e.g. Phase 2, 3, 4 for pairs).
        Each strategy defines its own phases and visualizations.
        
        Args:
            st: The Streamlit module.
            df_pair: Aligned price DataFrame for the selected assets.
            asset_a: Primary asset ticker.
            asset_b: Secondary asset ticker.
            params: Dict of parameters returned by render_parameters().
        """
        pass
