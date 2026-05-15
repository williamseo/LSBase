# lsbase/api_client/ls_api.py

import asyncio
import logging # 로깅 모듈 임포트
from typing import Any, Dict, AsyncGenerator, Optional
from ..core.api_interface import TradingAPI
from ..core.exceptions import APIRequestError, AuthenticationError, InvalidInputError, NetworkError
from ..openapi_client.OpenApi import OpenApi, ResponseValue
from ..core.spec_models import TrSpec

# 모듈 레벨 로거 설정
logger = logging.getLogger(__name__)

class LSTradingAPI(TradingAPI):
    def __init__(self, open_api_client: OpenApi):
        self._client = open_api_client

    async def query(self, tr_code: str, params: Dict[str, Any], tr_cont: str = "N", tr_cont_key: str = "") -> ResponseValue:
        # InBlock(요청) 데이터 로그 (DEBUG 레벨)
        logger.debug(f"[Request] TR: {tr_code}, InBlock: {params}")
        
        try:
            response = await self._client.request(tr_code, params, tr_cont=tr_cont, tr_cont_key=tr_cont_key)
            
            # 응답이 아예 없는 경우 (네트워크 타임아웃 등)
            if not response:
                raise NetworkError(self._client.last_message, tr_code=tr_code)

            # OutBlock(응답) 데이터 로그 (DEBUG 레벨)
            logger.debug(f"[Response] TR: {tr_code}, OutBlock: {response.body}")
            
            rsp_cd = response.body.get("rsp_cd")
            # 성공이 아닌 모든 경우
            #if rsp_cd != "00000":
            if not rsp_cd.startswith("00"):
                msg = response.body.get("rsp_msg", "알 수 없는 오류")
                # 특정 에러 코드에 따라 예외를 분기
                if rsp_cd == "IGW00121": # 예시: 인증 토큰 오류 코드
                    raise AuthenticationError(msg, rsp_cd=rsp_cd, tr_code=tr_code)
                if rsp_cd == "APBK0042": # 예시: 입력값 오류 코드
                    raise InvalidInputError(msg, rsp_cd=rsp_cd, tr_code=tr_code)
                
                # 그 외 일반적인 API 오류
                raise APIRequestError(msg, rsp_cd=rsp_cd, tr_code=tr_code)
                
            return response
        
        except asyncio.TimeoutError as e: # aiohttp 타임아웃 처리
            raise NetworkError(f"Request timed out: {e}", tr_code=tr_code) from e

    async def continuous_query(
        self, tr_code: str, params: Dict[str, Any],
        spec: Optional[TrSpec] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        tr_cont = "N"
        tr_cont_key = ""

        if spec and spec.continuation:
            gen = self._continuous_with_spec(tr_code, params, spec, tr_cont, tr_cont_key)
        else:
            gen = self._continuous_heuristic(tr_code, params, tr_cont, tr_cont_key)

        async for item in gen:
            yield item

    async def _continuous_with_spec(
        self, tr_code: str, params: Dict[str, Any],
        spec: TrSpec, tr_cont: str, tr_cont_key: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        cont = spec.continuation
        in_block_key = next((k for k in params if k.endswith("InBlock")), None)

        while True:
            try:
                response = await self.query(tr_code, params, tr_cont=tr_cont, tr_cont_key=tr_cont_key)
            except APIRequestError as e:
                logger.error("continuous query error for %s: %s", tr_code, e)
                break

            batch = response.body.get(cont.data_block, [])
            if not batch:
                break
            for item in batch:
                yield item

            if response.tr_cont != "Y":
                break
            tr_cont = response.tr_cont
            tr_cont_key = response.tr_cont_key

            if in_block_key:
                params, should_continue = cont.extract_next_params(
                    response.body, params, in_block_key,
                )
                if not should_continue:
                    break

            await asyncio.sleep(0.5)

    async def _continuous_heuristic(
        self, tr_code: str, params: Dict[str, Any],
        tr_cont: str, tr_cont_key: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        while True:
            try:
                response = await self.query(tr_code, params, tr_cont=tr_cont, tr_cont_key=tr_cont_key)
            except APIRequestError as e:
                logger.error("continuous query error for %s: %s", tr_code, e)
                break

            out_block_key = f"{tr_code}OutBlock1"
            batch = response.body.get(out_block_key, [])
            if not batch:
                break
            for item in batch:
                yield item

            if response.tr_cont != "Y":
                break
            tr_cont = response.tr_cont
            tr_cont_key = response.tr_cont_key

            continuation_data = response.body.get(f"{tr_code}OutBlock")
            in_block_key = next((k for k in params if k.endswith("InBlock")), None)

            if isinstance(continuation_data, dict) and in_block_key:
                updated = False
                for key, next_value in continuation_data.items():
                    if key not in params[in_block_key]:
                        continue
                    if isinstance(next_value, str) and not next_value.strip():
                        break
                    if key == "idx":
                        try:
                            if int(float(str(next_value))) == 0:
                                break
                        except (ValueError, TypeError):
                            pass
                    params[in_block_key][key] = next_value
                    updated = True
                    break
                if not updated:
                    break
            else:
                break

            await asyncio.sleep(0.5)            

    async def subscribe_realtime(self, tr_code: str, tr_key: str) -> bool:
        return await self._client.add_realtime(tr_code, tr_key)

    async def unsubscribe_realtime(self, tr_code: str, tr_key: str) -> bool:
        return await self._client.remove_realtime(tr_code, tr_key)
