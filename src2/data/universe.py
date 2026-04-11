import json
from pathlib import Path
from datetime import datetime
import pandas as pd
from typing import List, Dict, Optional, Any, Union

UNIVERSE_DIR = Path("data/universes")
UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)

class UniverseManager:
    """
    Manages Universe configuration files (JSON).
    """

    @staticmethod
    def list_universes() -> List[Dict[str, Any]]:
        """Returns metadata for all available universes."""
        universes = []
        if not UNIVERSE_DIR.exists():
            return []
            
        for f in UNIVERSE_DIR.glob("*.json"):
            try:
                with open(f, "r") as json_file:
                    data = json.load(json_file)
                    # Add filename for reference
                    data["filename"] = f.name
                    # Basic validation
                    if "name" in data and "symbols" in data:
                        universes.append(data)
            except Exception as e:
                print(f"Error reading universe {f}: {e}")
        return universes

    @staticmethod
    def save_universe(
        name: str, 
        symbols: List[str], 
        timeframe: str, 
        start_date: datetime, 
        end_date: datetime, 
        description: str = "",
        exchange_id: str = "binance"
    ) -> Path:
        """Saves a new universe configuration."""
        
        # Sanitize name
        safe_name = "".join([c if c.isalnum() else "_" for c in name])
        
        config = {
            "name": name,
            "description": description,
            "timeframe": timeframe,
            "data_source": exchange_id,
            "range": {
                "start": start_date.strftime("%Y-%m-%d %H:%M:%S"),
                "end": end_date.strftime("%Y-%m-%d %H:%M:%S")
            },
            "symbols": symbols,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "alignment_check": "unchecked"  # Default
        }
        
        filepath = UNIVERSE_DIR / f"{safe_name}.json"
        
        with open(filepath, "w") as f:
            json.dump(config, f, indent=4)
            
        return filepath

    @staticmethod
    def delete_universe(filename: str):
        path = UNIVERSE_DIR / filename
        if path.exists():
            path.unlink()

    @staticmethod
    def load_universe_config(filename: str) -> Optional[Dict]:
        path = UNIVERSE_DIR / filename
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
        return None

    @staticmethod
    def remove_symbols_from_universe(filename: str, symbols_to_remove: List[str]):
        """
        Removes a list of symbols from a universe file.
        """
        path = UNIVERSE_DIR / filename
        if not path.exists():
            return
            
        try:
            with open(path, "r") as f:
                data = json.load(f)
                
            original_count = len(data.get("symbols", []))
            # Filter out symbols
            data["symbols"] = [s for s in data.get("symbols", []) if s not in symbols_to_remove]
            new_count = len(data["symbols"])
            
            if original_count != new_count:
                # Save back
                with open(path, "w") as f:
                    json.dump(data, f, indent=4)
                    
        except Exception as e:
            print(f"Error updating universe {filename}: {e}")

    @staticmethod
    def update_universe(filename: str, updates: Dict[str, Any]) -> bool:
        """
        Updates an existing universe configuration with the provided fields.
        Preserves original fields not in `updates`.
        """
        path = UNIVERSE_DIR / filename
        if not path.exists():
            return False
            
        try:
            with open(path, "r") as f:
                data = json.load(f)
                
            # Update fields
            # Special handling for range to ensure structure
            if "range" in updates and isinstance(updates["range"], dict):
                data["range"].update(updates["range"])
                del updates["range"] # Handled
                
            data.update(updates)
            data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with open(path, "w") as f:
                json.dump(data, f, indent=4)
                
            return True
        except Exception as e:
            print(f"Error updating universe {filename}: {e}")
            return False
