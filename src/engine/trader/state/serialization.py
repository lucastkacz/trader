"""JSON serialization helpers for trader state payloads."""

import json
from typing import Any


def json_default(value: Any) -> Any:
    """Convert scalar library values into JSON-native types."""
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def dumps_json(value: Any) -> str:
    """Serialize state payloads with stable key ordering."""
    return json.dumps(value, sort_keys=True, default=json_default)
