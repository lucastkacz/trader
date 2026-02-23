import json
import os
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
    def save_basket(cls, name: str, pairs: List[Dict[str, Any]], universe_name: str, timeframe: str) -> str:
        """
        Saves a list of dictionaries containing asset pairs and their stats.
        Returns the path of the saved file.
        """
        cls._ensure_dir()
        filename = f"{name.replace(' ', '_').lower()}.json"
        filepath = os.path.join(cls.BASKETS_DIR, filename)

        data = {
            "name": name,
            "universe_name": universe_name,
            "timeframe": timeframe,
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
