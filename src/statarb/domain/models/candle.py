from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

class Candle(BaseModel):
    """
    Canonical representation of a single OHLCV candle.
    
    Attributes:
        timestamp: Start time of the candle (UTC).
        open: Opening price.
        high: Highest price.
        low: Lowest price.
        close: Closing price.
        volume: Base asset volume.
        quote_volume: Quote asset volume (optional, but recommended).
        trades: Number of trades (optional).
    """
    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Optional[Decimal] = None
    trades: Optional[int] = None
