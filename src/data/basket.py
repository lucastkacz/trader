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
    def get_dir(cls, basket_type: str = "") -> str:
        """Returns the specific directory for the basket type, creating it if necessary."""
        target_dir = os.path.join(cls.BASKETS_DIR, basket_type) if basket_type else cls.BASKETS_DIR
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        return target_dir

    @classmethod
    def save_basket(cls, name: str, pairs: List[Dict[str, Any]], universe_name: str, timeframe: str, 
                    basket_type: str = "strategy", metadata: Dict[str, Any] = None) -> str:
        """
        Saves a list of dictionaries containing asset pairs and their stats.
        Returns the path of the saved file.
        """
        target_dir = cls.get_dir(basket_type)
        filename = f"{name.replace(' ', '_').lower()}.json"
        filepath = os.path.join(target_dir, filename)

        data = {
            "name": name,
            "basket_type": basket_type,
            "created_at": datetime.now().isoformat(),
            "universe_name": universe_name,
            "timeframe": timeframe,
            "metadata": metadata or {},
            "pairs": pairs
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Basket saved to {filepath}")
        return filepath

    @classmethod
    def list_baskets(cls, basket_type: str = None) -> List[Dict[str, Any]]:
        """
        Returns a list of metadata for all saved baskets, optionally filtered by type.
        """
        baskets = []
        # Check specific type dir, or check all (correlated, strategy, and root)
        types_to_check = [basket_type] if basket_type else ["correlated", "strategy", ""]
        
        for b_type in types_to_check:
            dir_path = os.path.join(cls.BASKETS_DIR, b_type) if b_type else cls.BASKETS_DIR
            if os.path.exists(dir_path):
                for filename in os.listdir(dir_path):
                    if filename.endswith(".json"):
                        filepath = os.path.join(dir_path, filename)
                        try:
                            with open(filepath, 'r') as f:
                                data = json.load(f)
                                # Retroactively fix missing basket_type
                                if "basket_type" not in data:
                                    data["basket_type"] = b_type if b_type else "unknown"
                                baskets.append(data)
                        except Exception as e:
                            print(f"Error loading {filename}: {e}")
        return baskets

    @classmethod
    def load_basket(cls, name: str) -> Dict[str, Any]:
        """
        Loads a specific basket by its exact name.
        """
        baskets = cls.list_baskets()
        for b in baskets:
            if b.get("name") == name:
                return b
        return {}

    @classmethod
    def delete_basket(cls, name: str) -> bool:
        """
        Deletes a specific basket file by its exact name, scanning all directories.
        """
        filename = f"{name.replace(' ', '_').lower()}.json"
        
        for b_type in ["correlated", "strategy", ""]:
            dir_path = os.path.join(cls.BASKETS_DIR, b_type) if b_type else cls.BASKETS_DIR
            filepath = os.path.join(dir_path, filename)
            
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    return True
                except Exception as e:
                    print(f"Error deleting {filename}: {e}")
                    return False
        return False
