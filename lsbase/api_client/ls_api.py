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
            
            in_block_key = f"{tr_code}InBlock"
            
            if isinstance(continuation_data, dict) and in_block_key in params:
                # t1404의 'cts_shcode' 처리: 서버가 준 값을 그대로 사용해야 하므로 .strip()을 적용하지 않음
                if 'cts_shcode' in continuation_data and 'cts_shcode' in params[in_block_key]:
                    next_cts_key = continuation_data['cts_shcode']
                    
                    # 키가 비어있거나 공백으로만 채워져 있으면 종료 (이때만 .strip()으로 내용물 확인)
                    if not next_cts_key.strip():
                        break
                        
                    params[in_block_key]['cts_shcode'] = next_cts_key
                    logger.debug(f"다음 연속 조회를 위해 'cts_shcode'를 '{next_cts_key}'로 업데이트합니다.")
                
                # t1444의 'idx' 처리: int 또는 str 타입이 올 수 있으므로 str()로 변환 후 .strip() 적용
                elif 'idx' in continuation_data and 'idx' in params[in_block_key]:
                    raw_idx_key = str(continuation_data['idx']).strip()

                    try:
                        # 1. 실수/문자열을 float으로 처리하여 실수 포맷 제거 후 int로 변환
                        int_idx = int(float(raw_idx_key))
                    except ValueError:
                        # 변환 불가능하면 종료
                        logger.debug(f"t1444 연속 조회를 종료합니다. (IDX 값 변환 실패 또는 종료 키: '{raw_idx_key}')")
                        break

                    # 2. 다음 요청 키가 0이면 데이터가 없다는 뜻이므로 종료
                    if int_idx == 0:
                        logger.debug(f"t1444 연속 조회를 종료합니다. (Next idx is 0)")
                        break

                    next_idx_key = int_idx

                    params[in_block_key]['idx'] = next_idx_key
                    logger.debug(f"다음 연속 조회를 위해 'idx'를 '{next_idx_key}'로 (INT) 업데이트합니다.")


            await asyncio.sleep(1)

    async def subscribe_realtime(self, tr_code: str, tr_key: str) -> bool:
        return await self._client.add_realtime(tr_code, tr_key)

    async def unsubscribe_realtime(self, tr_code: str, tr_key: str) -> bool:
        return await self._client.remove_realtime(tr_code, tr_key)
