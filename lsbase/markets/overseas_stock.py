from ..core.base import MarketBase
from ..core.enum import RealtimeType
from ..core.models import OrderResponse, OverseasQuote
from ..core.exceptions import APIRequestError
from ..core.spec_models import SpecRepository

REALTIME_TR_MAP = {
    RealtimeType.EXECUTION: "GSC",
    RealtimeType.HOGA: "GSH",
}

class OverseasStockMarket(MarketBase):
    def __init__(self, api, repo: SpecRepository, account_no, account_pw):
        super().__init__(api, account_no=account_no, account_pw=account_pw)
        self._repo = repo

    async def get_quote(self, symbol: str, exchcd: str = "82") -> OverseasQuote:
        tr = self._repo["g3101"]
        keysymbol = f"{exchcd}{symbol}"
        params = tr.build_request({
            "delaygb": "R", "keysymbol": keysymbol,
            "exchcd": exchcd, "symbol": symbol,
        })
        try:
            response = await self._api.query(tr.code, params)
            parsed = tr.parse_response(response.body)
            data = parsed.get("g3101OutBlock", {})
            return OverseasQuote.model_validate(data)
        except APIRequestError as e:
            raise ConnectionError(f"overseas quote failed ({symbol}): {e}") from e

    async def place_order(self, symbol: str, quantity: int, price: float, side: str = "2") -> OrderResponse:
        tr = self._repo["COSAT00301"]
        params = tr.build_request({
            "RecCnt": 0, "OrdPtnCode": "00", "OrgOrdNo": 0,
            "OrdMktCode": "00", "IsuNo": symbol,
            "OrdQty": quantity, "OvrsOrdPrc": str(price),
            "OrdprcPtnCode": "00", "BrkTpCode": "0",
        })
        try:
            response = await self._api.query(tr.code, params)
            rsp_cd = response.body.get("rsp_cd", "")
            is_success = rsp_cd.startswith("00")
            order_id = ""
            if is_success:
                parsed = tr.parse_response(response.body)
                order_id = str(parsed.get("COSAT00301OutBlock2", {}).get("OrdNo", ""))
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
