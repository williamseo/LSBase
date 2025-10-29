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
    MARKET_STATUS = "MARKET_STATUS" # 장운영 상태 (JIF)
    NEWS_HEADLINE = "NEWS_HEADLINE" # 장운영 상태 (JIF)
