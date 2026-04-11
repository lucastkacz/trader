from enum import Enum, auto

class Side(Enum):
    LONG = 1
    SHORT = -1
    FLAT = 0

class TradeType(Enum):
    ENTRY = auto()
    EXIT = auto()
    REBALANCE = auto()

class OrderType(Enum):
    MARKET = auto()
    LIMIT = auto()
    STOP = auto()
