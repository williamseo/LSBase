# lsbase/core/base.py

from abc import ABC, abstractmethod
from .api_interface import TradingAPI
from .enum import OrderSide, OrderType, RealtimeType
from .models import OrderResponse, AccountBalanceSummary, Quote

class MarketBase(ABC):
    def __init__(self, api: TradingAPI, **kwargs):
        self._api = api
        self.account_no = kwargs.get('account_no')
        self.account_pw = kwargs.get('account_pw')

    @abstractmethod
    async def place_order(self, symbol: str, quantity: int, price: int, side: OrderSide, order_type: OrderType) -> OrderResponse:
        pass

    @abstractmethod
    async def modify_order(self, org_order_no: str, symbol: str, quantity: int, price: int) -> OrderResponse:
        pass

    @abstractmethod
    async def cancel_order(self, org_order_no: str, symbol: str, quantity: int) -> OrderResponse:
        pass

    @abstractmethod
    async def get_account_balance(self) -> AccountBalanceSummary:
        pass
    
    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote:
        pass

    @abstractmethod
    async def subscribe_realtime(self, symbol: str, data_type: RealtimeType):
        pass
