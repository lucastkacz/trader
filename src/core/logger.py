import sys
from typing import Optional
from pydantic import BaseModel, ConfigDict
from loguru import logger as _logger

from src.core.config import settings

class LogContext(BaseModel):
    """
    Strict validation model to guarantee that the JSONL logs
    are not polluted with arbitrary unstructured string data.
    All dynamic bindings MUST pass through this class.
    """
    # Prevent hallucinations by rejecting extra fields
    model_config = ConfigDict(extra="forbid")

    pair: Optional[str] = None
    trade_id: Optional[str] = None
    signal: Optional[str] = None
    # Add other rigidly allowed telemetry fields here over time

# Expose a clean configured logger module-wide
logger = _logger

def configure_logger(log_path: str = "logs/engine.jsonl", env: str = settings.env) -> None:
    """
    Mounts the Dual-Sink (Console + JSONLines) architected in PLAN 01_dual_sink_logging.
    Must be called exactly once during boot or testing.
    """
    # Clean default handlers
    logger.remove()

    if env != "test":
        # Sink A: Console (For local debugging)
        logger.add(
            sys.stdout,
            colorize=True,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
            level="DEBUG" if env == "dev" else "INFO"
        )

    # Sink B: JSON Lines output (For AI Parsers and auditing)
    # Mandate: enqueue=True ensures Process/Thread safety when SQLite crashes.
    # Mandate: diagnose=False acts as an OOM Shield, preventing multi-GB tracebacks.
    logger.add(
        log_path,
        serialize=True,     # Forces pure JSON format representation per line
        rotation="00:00",   # Daily rollover
        retention="30 days",# Retention policy
        enqueue=True,       # Background thread (Safety wrapper)
        backtrace=True,     # Show standard error path
        diagnose=False,      # (OOM SHIELD) Never dump full variable context into RAM!
        level="DEBUG"
    )

# Optionally auto-configure the logger safely upon loading the module, 
# although manual initialization is better for tests.
if settings.env != "test":
    configure_logger()
