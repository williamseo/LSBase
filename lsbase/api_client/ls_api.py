# lsbase/api_client/ls_api.py

import asyncio
from typing import Any, List, Dict, AsyncGenerator
from ..core.api_interface import TradingAPI
from ..core.exceptions import APIRequestError
from ..openapi_client.OpenApi import OpenApi, ResponseValue

class LSTradingAPI(TradingAPI):
    def __init__(self, open_api_client: OpenApi):
        self._client = open_api_client

    async def query(self, tr_code: str, params: Dict[str, Any], tr_cont: str = "N", tr_cont_key: str = "") -> ResponseValue:
        response = await self._client.request(tr_code, params, tr_cont=tr_cont, tr_cont_key=tr_cont_key)
        
        if not response or response.body.get("rsp_cd") != "00000":
            msg = response.body.get("rsp_msg") if response and response.body else self._client.last_message
            rsp_cd = response.body.get("rsp_cd") if response and response.body else None
            raise APIRequestError(msg, rsp_cd=rsp_cd)
            
        return response

    async def continuous_query(self, tr_code: str, params: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        tr_cont = "N"
        page_idx = 0
        page_size = 50  # API 페이지 크기

        while True:
            offset = page_idx * page_size
            current_params = params.copy()
            in_block_key = f"{tr_code}InBlock"

            if in_block_key in current_params and "idx" in current_params[in_block_key]:
                current_params[in_block_key]["idx"] = offset
            
            try:
                response = await self.query(tr_code, current_params, tr_cont=tr_cont, tr_cont_key=str(offset))
            except APIRequestError as e:
                print(f"연속 조회 중 오류 발생: {e}")
                break

            out_block_key = f"{tr_code}OutBlock1"
            batch = response.body.get(out_block_key, [])
            if not batch:
                break

            for item in batch:
                yield item

            if response.tr_cont != "Y":
                break
            
            tr_cont = "Y"
            page_idx += 1
            await asyncio.sleep(0.5)  # API Throttling

    async def subscribe_realtime(self, tr_code: str, tr_key: str) -> bool:
        return await self._client.add_realtime(tr_code, tr_key)

    async def unsubscribe_realtime(self, tr_code: str, tr_key: str) -> bool:
        return await self._client.remove_realtime(tr_code, tr_key)
