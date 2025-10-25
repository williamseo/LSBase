from enum import Enum

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"

class RealtimeType(str, Enum):
    EXECUTION = "EXECUTION"
    HOGA = "HOGA"
    ORDER_STATUS = "ORDER_STATUS"
