import json
import os
from datetime import datetime
from typing import List, Dict, Any

class BasketManager:
    """
    Manages the saving and loading of 'Baskets' (sets of proven cointegrated pairs)
    extracted during the Alpha Discovery phase.
    """
    BASKETS_DIR = "data/baskets"

    @classmethod
    def _ensure_dir(cls):
        if not os.path.exists(cls.BASKETS_DIR):
            os.makedirs(cls.BASKETS_DIR)

    @classmethod
    def save_basket(cls, name: str, pairs: List[Dict[str, Any]], universe_name: str, timeframe: str, 
                    corr_lookback: int = 0, coint_window: int = 0, start_date: str = "", end_date: str = "",
                    correlation_method: str = "Not Specified") -> str:
        """
        Saves a list of dictionaries containing asset pairs and their stats.
        Returns the path of the saved file.
        """
        cls._ensure_dir()
        filename = f"{name.replace(' ', '_').lower()}.json"
        filepath = os.path.join(cls.BASKETS_DIR, filename)

        data = {
            "name": name,
            "created_at": datetime.now().isoformat(),
            "universe_name": universe_name,
            "timeframe": timeframe,
            "metadata": {
                "correlation_method": correlation_method,
                "correlation_lookback_periods": corr_lookback,
                "cointegration_window_periods": coint_window,
                "data_start_date": start_date,
                "data_end_date": end_date
            },
            "pairs": pairs
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Basket saved to {filepath}")
        return filepath

    @classmethod
    def list_baskets(cls) -> List[Dict[str, Any]]:
        """
        Returns a list of metadata for all saved baskets.
        """
        cls._ensure_dir()
        baskets = []
        for filename in os.listdir(cls.BASKETS_DIR):
            if filename.endswith(".json"):
                filepath = os.path.join(cls.BASKETS_DIR, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        baskets.append(data)
                except Exception as e:
                    print(f"Error loading {filename}: {e}")
        return baskets

    @classmethod
    def load_basket(cls, name: str) -> Dict[str, Any]:
        """
        Loads a specific basket by its exact name.
        """
        cls._ensure_dir()
        baskets = cls.list_baskets()
        for b in baskets:
            if b.get("name") == name:
                return b
        return {}

    @classmethod
    def delete_basket(cls, name: str) -> bool:
        """
        Deletes a specific basket file by its exact name.
        """
        filename = f"{name.replace(' ', '_').lower()}.json"
        filepath = os.path.join(cls.BASKETS_DIR, filename)
        
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                return True
            except Exception as e:
                print(f"Error deleting {filename}: {e}")
                return False
        return False
