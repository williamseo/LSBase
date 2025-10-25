# lsbase/core/base.py

from abc import ABC, abstractmethod
from .api_interface import TradingAPI
from .enum import OrderSide, OrderType, RealtimeType
from .models import OrderResult, Balance

class MarketBase(ABC):
    def __init__(self, api: TradingAPI, account_no: str, account_pw: str):
        self._api = api
        self.account_no = account_no
        self.account_pw = account_pw

    @abstractmethod
    async def place_order(self, symbol: str, quantity: int, price: int, side: OrderSide, order_type: OrderType) -> OrderResult:
        pass

    @abstractmethod
    async def modify_order(self, org_order_no: str, symbol: str, quantity: int, price: int) -> OrderResult:
        pass

    @abstractmethod
    async def cancel_order(self, org_order_no: str, symbol: str, quantity: int) -> OrderResult:
        pass

    @abstractmethod
    async def get_account_balance(self) -> Balance:
        pass
    
    @abstractmethod
    async def get_quote(self, symbol: str) -> dict:
        pass

    @abstractmethod
    async def subscribe_realtime(self, symbol: str, data_type: RealtimeType):
        pass
