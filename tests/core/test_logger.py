import json
import logging
import pytest
from pydantic import ValidationError
from typing import Dict, Any

# We are following the TDD flow strictly.
# The code in src/ does not exist yet. 

try:
    from src.core.logger import LogContext, logger, configure_logger
except ImportError:
    pass # Will fail in the next step naturally


def test_log_context_validation():
    """
    Ensures that the Pydantic metadata schema strictly blocks invalid
    or hallucinated fields, enforcing the Binding Mandate.
    """
    # 1. Valid Context
    valid = LogContext(pair="BTC/USDT", trade_id="12345")
    assert valid.pair == "BTC/USDT"
    
    # 2. Invalid Context (Using arbitrary hallucinated fields)
    with pytest.raises(ValidationError):
        # We expect this to crash because "some_random_field" is not allowed in our schema.
        LogContext(pair="ETH/USDT", some_random_field="this is an error")

def test_jsonl_output_format(tmp_path):
    """
    Verifies that the logger correctly flattens the LogContext into a pure
    JSONLines output on disk, proving the Anti-String metadata rule.
    """
    log_file = tmp_path / "test.jsonl"
    
    # Needs to configure the logger locally for testing
    configure_logger(log_path=str(log_file), env="test")
    
    # Execute a bound log
    context = LogContext(pair="SOL/USDT")
    logger.bind(**context.model_dump(exclude_none=True)).debug("Initiating Z-Score execution.")
    
    # In tests or fast crash scenarios, we use complete() to drain the background thread enqueue
    logger.complete()
    
    with open(log_file, "r") as f:
        log_line = f.readline()
        
    data: Dict[str, Any] = json.loads(log_line)
    
    assert data["record"]["level"]["name"] == "DEBUG"
    assert data["record"]["message"] == "Initiating Z-Score execution."
    # The crucial part: the metadata must be dynamically bound, not hardcoded into the message
    assert data["record"]["extra"]["pair"] == "SOL/USDT"
