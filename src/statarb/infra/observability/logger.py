import logging
import sys
from pathlib import Path

def setup_logger(name: str = "quant_logger", level: int = logging.DEBUG) -> logging.Logger:
    """
    Configures and returns a logger that writes to console and a debug file.
    """
    logger = logging.getLogger(name)
    
    if logger.hasHandlers():
        return logger
        
    logger.setLevel(level)

    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO) # Keep console clean
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler (Debug)
    file_handler = logging.FileHandler("debug_fetch.log", mode='w')
    file_handler.setLevel(logging.DEBUG) # File gets everything
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
