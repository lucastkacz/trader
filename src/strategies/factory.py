import importlib
import os
import yaml
from typing import Dict, Any, Type
from src.strategies.base import BaseStrategy

class StrategyFactory:
    """
    Factory class responsible for dynamically instantiating trading strategies 
    based on their configuration files.
    """
    
    # Registry mapping strategy names (from config) to their fully qualified class paths
    STRATEGY_REGISTRY = {
        "Pairs Trading (Classic Cointegration)": "src.strategies.pairs.strategy.PairsTradingStrategy",
    }

    @classmethod
    def load_config(cls, config_path: str) -> Dict[str, Any]:
        """Loads a YAML configuration file."""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Strategy configuration file not found at: {config_path}")
            
        with open(config_path, 'r') as file:
            try:
                config = yaml.safe_load(file)
            except yaml.YAMLError as exc:
                raise ValueError(f"Error parsing YAML config: {exc}")
                
        return config

    @classmethod
    def get_strategy_class(cls, strategy_name: str) -> Type[BaseStrategy]:
        """Dynamically imports and returns the strategy class based on registry."""
        if strategy_name not in cls.STRATEGY_REGISTRY:
            raise KeyError(f"Strategy '{strategy_name}' is not registered in the StrategyFactory.")
            
        module_path, class_name = cls.STRATEGY_REGISTRY[strategy_name].rsplit('.', 1)
        module = importlib.import_module(module_path)
        strategy_class = getattr(module, class_name)
        
        if not issubclass(strategy_class, BaseStrategy):
            raise TypeError(f"Class {class_name} must inherit from BaseStrategy.")
            
        return strategy_class

    @classmethod
    def get_default_config(cls, strategy_name: str) -> Dict[str, Any]:
        """
        Derives the path to the strategy's config.yml from the registry and loads it.
        """
        if strategy_name not in cls.STRATEGY_REGISTRY:
            raise KeyError(f"Strategy '{strategy_name}' is not registered.")
            
        # Extract module path: e.g. "src.strategies.pairs.strategy.PairsTradingStrategy"
        module_path = cls.STRATEGY_REGISTRY[strategy_name].rsplit('.', 2)[0] # gives "src.strategies.pairs"
        
        # Convert dot path to file path relative to project root
        dir_path = module_path.replace(".", os.sep)
        config_path = os.path.join(dir_path, "config.yml")
        
        return cls.load_config(config_path)

    @classmethod
    def create(cls, config: Dict[str, Any]) -> BaseStrategy:
        """
        Creates and returns an instantiated strategy object.
        
        Args:
            config: The loaded configuration dictionary.
            
        Returns:
            An instance of a class inheriting from BaseStrategy.
        """
        strategy_name = config.get("name")
        if not strategy_name:
            raise ValueError("Configuration file missing required 'name' key.")
            
        strategy_class = cls.get_strategy_class(strategy_name)
        return strategy_class(config)
