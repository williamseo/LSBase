from ..core.base import MarketBase
from ..core.enum import OrderSide, OrderType, RealtimeType
from ..core.models import OrderResponse, FuturesQuote
from ..core.exceptions import APIRequestError
from ..core.spec_models import SpecRepository

REALTIME_TR_MAP = {
    RealtimeType.EXECUTION: "FC0",  # KOSPI200선물체결
    RealtimeType.HOGA: "FH0",       # KOSPI200선물호가
}

class FuturesOptionsMarket(MarketBase):
    def __init__(self, api, repo: SpecRepository, account_no, account_pw):
        super().__init__(api, account_no=account_no, account_pw=account_pw)
        self._repo = repo

    async def get_quote(self, focode: str) -> FuturesQuote:
        tr = self._repo["t2101"]
        params = tr.build_request({"focode": focode})
        try:
            response = await self._api.query(tr.code, params)
            parsed = tr.parse_response(response.body)
            data = parsed.get("t2101OutBlock", {})
            return FuturesQuote.model_validate(data)
        except APIRequestError as e:
            raise ConnectionError(f"futures quote failed ({focode}): {e}") from e

    async def place_order(self, symbol: str, quantity: int, price: float, side: OrderSide, order_type: OrderType) -> OrderResponse:
        tr = self._repo["CFOAT00100"]
        bns_code = "2" if side == OrderSide.BUY else "1"
        price_code = "01" if order_type == OrderType.LIMIT else "03"
        params = tr.build_request({
            "FnoIsuNo": symbol,
            "BnsTpCode": bns_code,
            "FnoOrdprcPtnCode": price_code,
            "FnoOrdPrc": str(price),
            "OrdQty": quantity,
        })
        try:
            response = await self._api.query(tr.code, params)
            rsp_cd = response.body.get("rsp_cd", "")
            is_success = rsp_cd.startswith("00")
            order_id = ""
            if is_success:
                parsed = tr.parse_response(response.body)
                order_id = str(parsed.get("CFOAT00100OutBlock2", {}).get("OrdNo", ""))
            return OrderResponse(is_success=is_success, order_id=order_id, message=response.body.get("rsp_msg", ""))
        except APIRequestError as e:
            return OrderResponse(is_success=False, order_id="", message=str(e))

    async def modify_order(self, org_order_no: str, symbol: str, quantity: int, price: float) -> OrderResponse:
        tr = self._repo["CFOAT00200"]
        params = tr.build_request({
            "FnoIsuNo": symbol,
            "OrgOrdNo": org_order_no,
            "FnoOrdprcPtnCode": "00",
            "FnoOrdPrc": str(price),
            "MdfyQty": quantity,
        })
        try:
            response = await self._api.query(tr.code, params)
            rsp_cd = response.body.get("rsp_cd", "")
            is_success = rsp_cd.startswith("00")
            order_id = str(response.body.get("CFOAT00200OutBlock2", {}).get("OrdNo", "")) if is_success else ""
            return OrderResponse(is_success=is_success, order_id=order_id, message=response.body.get("rsp_msg", ""))
        except APIRequestError as e:
            return OrderResponse(is_success=False, order_id="", message=str(e))

    async def cancel_order(self, org_order_no: str, symbol: str, quantity: int) -> OrderResponse:
        tr = self._repo["CFOAT00300"]
        params = tr.build_request({
            "FnoIsuNo": symbol,
            "OrgOrdNo": org_order_no,
            "CancQty": quantity,
        })
        try:
            response = await self._api.query(tr.code, params)
            rsp_cd = response.body.get("rsp_cd", "")
            is_success = rsp_cd.startswith("00")
            return OrderResponse(is_success=is_success, order_id=org_order_no, message=response.body.get("rsp_msg", ""))
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
