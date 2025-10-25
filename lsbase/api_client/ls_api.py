# lsbase/api_client/ls_api.py

from ..core.api_interface import TradingAPI
from ..openapi_client.OpenApi import OpenApi, ResponseValue
from typing import Any, List, Dict

class LSTradingAPI(TradingAPI):
    def __init__(self, open_api_client: OpenApi):
        self._client = open_api_client

    async def query(self, tr_code: str, params: Dict[str, Any], tr_cont: str = "N", tr_cont_key: str = "") -> ResponseValue | None:
        return await self._client.request(tr_code, params, tr_cont=tr_cont, tr_cont_key=tr_cont_key)

    async def continuous_query(self, tr_code: str, params: Dict[str, Any], continuous_key_name: str = "cts_ord_no") -> List[Dict[str, Any]]:
        # 구현 필요
        pass

    async def subscribe_realtime(self, tr_code: str, tr_key: str) -> bool:
        return await self._client.add_realtime(tr_code, tr_key)

    async def unsubscribe_realtime(self, tr_code: str, tr_key: str) -> bool:
        return await self._client.remove_realtime(tr_code, tr_key)
