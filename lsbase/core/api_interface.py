# lsbase/core/api_interface.py

from abc import ABC, abstractmethod
from typing import Any, List, Dict
from ..openapi_client.OpenApi import ResponseValue

class TradingAPI(ABC):
    @abstractmethod
    async def query(self, tr_code: str, params: Dict[str, Any], tr_cont: str = "N", tr_cont_key: str = "") -> ResponseValue | None:
        pass

    @abstractmethod
    async def continuous_query(self, tr_code: str, params: Dict[str, Any], continuous_key_name: str = "cts_ord_no") -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def subscribe_realtime(self, tr_code: str, tr_key: str) -> bool:
        pass

    @abstractmethod
    async def unsubscribe_realtime(self, tr_code: str, tr_key: str) -> bool:
        pass
