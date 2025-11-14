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

    async def continuous_query(self, tr_code: str, params: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        tr_cont = "N"
        tr_cont_key = ""

        while True:
            try:
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

            if response.tr_cont != "Y":
                break
            
            tr_cont = response.tr_cont
            tr_cont_key = response.tr_cont_key
            
            continuation_out_block_key = f"{tr_code}OutBlock"
            continuation_data = response.body.get(continuation_out_block_key)
            
            # InBlock 키는 TR 코드와 이름 규칙이 다를 수 있으므로 params에서 직접 찾습니다.
            in_block_key = next((key for key in params if key.endswith("InBlock")), None)
            
            if isinstance(continuation_data, dict) and in_block_key:
                is_key_updated = False
                
                # OutBlock의 모든 키에 대해 반복 (e.g., 'cts_date', 'shcode', ...)
                for key, next_value in continuation_data.items():
                    # 해당 키가 InBlock에도 존재한다면, 연속 조회 키로 간주
                    if key in params[in_block_key]:
                        
                        # 값이 비어있으면 연속 조회 종료
                        if isinstance(next_value, str) and not next_value.strip():
                            logger.debug(f"연속 조회 키 '{key}'가 비어있어 조회를 종료합니다.")
                            is_key_updated = False
                            break
                            
                        # 특정 키 'idx'가 0이면 종료 (기존 로직 유지)
                        if key == 'idx':
                            try:
                                if int(float(str(next_value))) == 0:
                                    logger.debug("다음 idx가 0이므로 조회를 종료합니다.")
                                    is_key_updated = False
                                    break
                            except (ValueError, TypeError):
                                pass

                        # 다음 요청을 위해 InBlock의 파라미터 업데이트
                        params[in_block_key][key] = next_value
                        logger.debug(f"연속 조회를 위해 '{key}'를 '{next_value}'로 업데이트합니다.")
                        is_key_updated = True
                        # 가장 처음 발견된 공통 키를 연속 키로 간주하고 루프 탈출
                        break 
                
                if not is_key_updated:
                    break # 업데이트된 키가 없으면 전체 루프 종료
            else:
                break # OutBlock이나 InBlock 구조가 예상과 다르면 종료

            await asyncio.sleep(0.5) # API 부담을 줄이기 위해 0.5초 대기            

    async def subscribe_realtime(self, tr_code: str, tr_key: str) -> bool:
        return await self._client.add_realtime(tr_code, tr_key)

    async def unsubscribe_realtime(self, tr_code: str, tr_key: str) -> bool:
        return await self._client.remove_realtime(tr_code, tr_key)
