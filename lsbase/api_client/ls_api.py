import asyncio
import logging
from typing import Any, Dict, AsyncGenerator, Optional
from ..core.api_interface import TradingAPI
from ..core.exceptions import APIRequestError, AuthenticationError, InvalidInputError, NetworkError
from ..openapi_client.OpenApi import OpenApi, ResponseValue
from ..core.spec_models import TrSpec
from ..core.throttler import Throttler

logger = logging.getLogger(__name__)


class LSTradingAPI(TradingAPI):
    def __init__(self, open_api_client: OpenApi, throttler: Optional[Throttler] = None):
        self._client = open_api_client
        self._throttler = throttler or Throttler(rate=5.0, burst=5)

    async def query(self, tr_code: str, params: Dict[str, Any], tr_cont: str = "N", tr_cont_key: str = "") -> ResponseValue:
        await self._throttler.acquire()
        logger.debug(f"[Request] TR: {tr_code}, InBlock: {params}")

        try:
            response = await self._client.request(tr_code, params, tr_cont=tr_cont, tr_cont_key=tr_cont_key)

            if not response:
                raise NetworkError(self._client.last_message, tr_code=tr_code)

            logger.debug(f"[Response] TR: {tr_code}, OutBlock: {response.body}")

            rsp_cd = response.body.get("rsp_cd")
            if not rsp_cd.startswith("00"):
                msg = response.body.get("rsp_msg", "알 수 없는 오류")
                if rsp_cd == "IGW00121":
                    raise AuthenticationError(msg, rsp_cd=rsp_cd, tr_code=tr_code)
                if rsp_cd == "APBK0042":
                    raise InvalidInputError(msg, rsp_cd=rsp_cd, tr_code=tr_code)
                raise APIRequestError(msg, rsp_cd=rsp_cd, tr_code=tr_code)

            return response

        except asyncio.TimeoutError as e:
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

    async def subscribe_realtime(self, tr_code: str, tr_key: str) -> bool:
        return await self._client.add_realtime(tr_code, tr_key)

    async def unsubscribe_realtime(self, tr_code: str, tr_key: str) -> bool:
        return await self._client.remove_realtime(tr_code, tr_key)

    @property
    def throttler_stats(self) -> dict:
        return self._throttler.stats
