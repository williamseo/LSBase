# lsbase/api_client/ls_api.py

import asyncio
import logging # 로깅 모듈 임포트
from typing import Any, List, Dict, AsyncGenerator
from ..core.api_interface import TradingAPI
from ..core.exceptions import APIRequestError
from ..openapi_client.OpenApi import OpenApi, ResponseValue
from ..core.exceptions import APIRequestError, AuthenticationError, InvalidInputError, NetworkError

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
            if rsp_cd != "00000":
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
            
    async def continuous_query(self, tr_code: str, params: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        
        tr_cont = "N"    # 최초 조회 시에는 tr_cont가 "N"
        tr_cont_key = "" # 최초 조회 시에는 비워두거나 "0"

        while True:
            try:
                # 다음 페이지를 요청할 때는 이전 응답의 tr_cont, tr_cont_key를 사용
                response = await self.query(tr_code, params, tr_cont=tr_cont, tr_cont_key=tr_cont_key)
            except APIRequestError as e:
                logger.error(f"연속 조회 중 오류 발생: {e}")
                break

            out_block_key = f"{tr_code}OutBlock1"
            batch = response.body.get(out_block_key, [])
            if not batch:
                break

            for item in batch:
                yield item

            # 다음 조회가 없으면 루프 종료
            if response.tr_cont != "Y":
                break
            
            # 다음 조회를 위해 상태 업데이트
            tr_cont = response.tr_cont
            tr_cont_key = response.tr_cont_key
            
            # 일부 TR은 다음 페이지를 위해 입력값(idx)도 변경해야 할 수 있음
            # 이 부분은 TR 명세에 따라 추가적인 처리가 필요할 수 있음
            
            await asyncio.sleep(1)  # API Throttling

    async def subscribe_realtime(self, tr_code: str, tr_key: str) -> bool:
        return await self._client.add_realtime(tr_code, tr_key)

    async def unsubscribe_realtime(self, tr_code: str, tr_key: str) -> bool:
        return await self._client.remove_realtime(tr_code, tr_key)
