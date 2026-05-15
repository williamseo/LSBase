from ..core.base import MarketBase
from ..core.enum import RealtimeType
from ..core.models import OrderResponse, OverseasFuturesQuote
from ..core.exceptions import APIRequestError
from ..core.spec_models import SpecRepository

REALTIME_TR_MAP = {
    RealtimeType.EXECUTION: "OVC",
    RealtimeType.HOGA: "OVH",
}

class OverseasFuturesMarket(MarketBase):
    def __init__(self, api, repo: SpecRepository, account_no, account_pw):
        super().__init__(api, account_no=account_no, account_pw=account_pw)
        self._repo = repo

    async def get_quote(self, symbol: str) -> OverseasFuturesQuote:
        tr = self._repo["o3105"]
        params = tr.build_request({"symbol": symbol})
        try:
            response = await self._api.query(tr.code, params)
            parsed = tr.parse_response(response.body)
            data = parsed.get("o3105OutBlock", {})
            return OverseasFuturesQuote.model_validate(data)
        except APIRequestError as e:
            raise ConnectionError(f"overseas futures quote failed ({symbol}): {e}") from e

    async def place_order(self, symbol: str, quantity: int, price: float, side: str = "2") -> OrderResponse:
        tr = self._repo["CIDBT00100"]
        params = tr.build_request({
            "OrdDt": "", "IsuCodeVal": symbol,
            "FutsOrdTpCode": "0", "BnsTpCode": side,
            "AbrdFutsOrdPtnCode": "1", "CrcyCode": "USD",
            "OvrsDrvtOrdPrc": str(price), "CndiOrdPrc": "0",
            "OrdQty": quantity, "PrdtCode": symbol,
            "DueYymm": "", "ExchCode": "",
        })
        try:
            response = await self._api.query(tr.code, params)
            rsp_cd = response.body.get("rsp_cd", "")
            is_success = rsp_cd.startswith("00")
            order_id = str(response.body.get("CIDBT00100OutBlock2", {}).get("OvrsFutsOrdNo", "")) if is_success else ""
            return OrderResponse(is_success=is_success, order_id=order_id, message=response.body.get("rsp_msg", ""))
        except APIRequestError as e:
            return OrderResponse(is_success=False, order_id="", message=str(e))

    async def subscribe_realtime(self, key: str, data_type: RealtimeType) -> bool:
        tr_code = REALTIME_TR_MAP.get(data_type)
        if not tr_code:
            raise NotImplementedError(f"unsupported RealtimeType: {data_type}")
        return await self._api.subscribe_realtime(tr_code, key)

    async def unsubscribe_realtime(self, key: str, data_type: RealtimeType) -> bool:
        tr_code = REALTIME_TR_MAP.get(data_type)
        if not tr_code:
            raise NotImplementedError(f"unsupported RealtimeType: {data_type}")
        return await self._api.unsubscribe_realtime(tr_code, key)
