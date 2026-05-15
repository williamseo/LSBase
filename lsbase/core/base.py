from abc import ABC, abstractmethod
from typing import Optional
from .api_interface import TradingAPI
from .enum import OrderSide, OrderType, RealtimeType
from .models import OrderResponse, AccountBalanceSummary, Quote


class MarketBase(ABC):
    def __init__(self, api: TradingAPI, **kwargs):
        self._api = api
        self.account_no = kwargs.get('account_no')
        self.account_pw = kwargs.get('account_pw')

    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote:
        pass

    @abstractmethod
    async def place_order(self, symbol: str, quantity: int, price, side: OrderSide, order_type: OrderType) -> OrderResponse:
        pass

    async def modify_order(self, org_order_no: str, symbol: str, quantity: int, price
    ) -> OrderResponse:
        raise NotImplementedError(f"{type(self).__name__}.modify_order not implemented")

    async def cancel_order(self, org_order_no: str, symbol: str, quantity: int
    ) -> OrderResponse:
        raise NotImplementedError(f"{type(self).__name__}.cancel_order not implemented")

    async def get_account_balance(self) -> AccountBalanceSummary:
        raise NotImplementedError(f"{type(self).__name__}.get_account_balance not implemented")

    async def subscribe_realtime(self, symbol: str, data_type: RealtimeType) -> bool:
        raise NotImplementedError(f"{type(self).__name__}.subscribe_realtime not implemented")

    async def unsubscribe_realtime(self, symbol: str, data_type: RealtimeType) -> bool:
        raise NotImplementedError(f"{type(self).__name__}.unsubscribe_realtime not implemented")
