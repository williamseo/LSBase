# lsbase/core/api_interface.py

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, AsyncGenerator, Optional
from ..openapi_client.OpenApi import ResponseValue
from ..core.spec_models import TrSpec

class TradingAPI(ABC):
    @abstractmethod
    async def query(self, tr_code: str, params: Dict[str, Any], tr_cont: str = "N", tr_cont_key: str = "") -> ResponseValue | None:
        pass

    @abstractmethod
    async def continuous_query(
        self, tr_code: str, params: Dict[str, Any],
        spec: Optional[TrSpec] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        pass

    @abstractmethod
    async def subscribe_realtime(self, tr_code: str, tr_key: str) -> bool:
        pass

    @abstractmethod
    async def unsubscribe_realtime(self, tr_code: str, tr_key: str) -> bool:
        pass
