from ..core.base import MarketBase
from ..core.enum import OrderSide, OrderType, RealtimeType
from ..core.models import (
    OrderResponse, AccountBalanceSummary, Quote, MarketCapStock, HistoricalPrice
)
from ..core.exceptions import APIRequestError
from ..core.spec_models import SpecRepository, TrClass
from datetime import datetime


REALTIME_TR_MAP = {
    RealtimeType.EXECUTION: "S3_",
    RealtimeType.HOGA: "H1_",
    RealtimeType.MARKET_STATUS: "JIF",
    RealtimeType.NEWS_HEADLINE: "NWS",
}


class StockMarket(MarketBase):
    def __init__(self, api, repo: SpecRepository, account_no, account_pw):
        super().__init__(api, account_no=account_no, account_pw=account_pw)
        self._repo = repo

    async def get_quote(self, symbol: str) -> Quote:
        tr = self._repo["t1102"]
        request = tr.build_request({"shcode": symbol})
        try:
            response = await self._api.query(tr.code, request)
            parsed = tr.parse_response(response.body)
            data = parsed.get("t1102OutBlock", {})
            if not data:
                raise ValueError("t1102 OutBlock not found")
            return Quote.model_validate(data)
        except APIRequestError as e:
            raise ConnectionError(f"get_quote failed ({symbol}): {e}") from e

    async def place_order(self, symbol: str, quantity: int, price: int, side: OrderSide, order_type: OrderType) -> OrderResponse:
        tr = self._repo["CSPAT00601"]
        request = tr.build_request({
            "IsuNo": f"A{symbol}",
            "OrdQty": str(quantity),
            "OrdPrc": str(price),
            "BnsTpCode": "2" if side == OrderSide.BUY else "1",
            "OrdprcPtnCode": "03" if order_type == OrderType.MARKET else "00",
            "MgntrnCode": "000",
            "LoanDt": "",
            "OrdCndiTpCode": "0",
            "MbrNo": "NXT",
        })
        try:
            response = await self._api.query(tr.code, request)
            rsp_cd = response.body.get("rsp_cd", "")
            rsp_msg = response.body.get("rsp_msg", "")
            is_success = rsp_cd.startswith("00")
            order_id = ""
            if is_success:
                parsed = tr.parse_response(response.body)
                outblock2 = parsed.get("CSPAT00601OutBlock2", {})
                order_id = str(outblock2.get("OrdNo", ""))
            return OrderResponse(is_success=is_success, order_id=order_id, message=rsp_msg)
        except APIRequestError as e:
            return OrderResponse(is_success=False, order_id="", message=str(e))

    async def get_account_balance(self) -> AccountBalanceSummary:
        tr = self._repo["CSPAQ12200"]
        request = tr.build_request({
            "RecCnt": "0",
            "MgmtBrnNo": "",
            "BalCreTp": "0",
        })
        try:
            response = await self._api.query(tr.code, request)
            rsp_cd = response.body.get("rsp_cd", "")
            if not rsp_cd.startswith("00"):
                raise APIRequestError(response.body.get("rsp_msg", ""), rsp_cd=rsp_cd, tr_code=tr.code)
            parsed = tr.parse_response(response.body)
            outblock2 = parsed.get("CSPAQ12200OutBlock2", [])
            if isinstance(outblock2, list):
                if not outblock2:
                    raise ValueError("OutBlock2 empty")
                account_data = outblock2[0]
            else:
                account_data = outblock2
            return AccountBalanceSummary.model_validate(account_data)
        except (APIRequestError, ValueError, IndexError) as e:
            raise ConnectionError(f"get_account_balance failed: {e}") from e

    async def get_top_market_cap_stocks(self, market_type: str, limit: int = None) -> list[MarketCapStock]:
        if market_type.upper() not in ["KOSPI", "KOSDAQ"]:
            raise ValueError("market_type must be 'KOSPI' or 'KOSDAQ'")
        tr = self._repo["t1444"]
        upcode = "001" if market_type.upper() == "KOSPI" else "301"
        request = tr.build_request({"upcode": upcode, "idx": 0})
        all_stocks = []
        rank = 1
        try:
            data_block = tr.continuation.data_block if tr.continuation else "t1444OutBlock1"
            async for item_dict in self._api.continuous_query(tr.code, request, spec=tr):
                stock_info = MarketCapStock(
                    rank=rank,
                    name=item_dict.get("hname", ""),
                    code=item_dict.get("shcode", ""),
                    price=int(item_dict.get("price", 0)),
                    market_cap_in_b_krw=int(item_dict.get("total", 0)),
                )
                all_stocks.append(stock_info)
                if limit is not None and len(all_stocks) >= limit:
                    break
                rank += 1
            return all_stocks
        except APIRequestError as e:
            raise ConnectionError(f"get_top_market_cap_stocks failed: {e}") from e

    async def modify_order(self, org_order_no: str, symbol: str, quantity: int, price: int) -> OrderResponse:
        tr_code = "CSPAT00701"
        tr = self._repo.get(tr_code)
        if tr is None:
            return OrderResponse(is_success=False, order_id="", message=f"TR '{tr_code}' not in spec")
        request = tr.build_request({
            "OrgOrdNo": org_order_no,
            "IsuNo": f"A{symbol}",
            "OrdprcPtnCode": "00",
            "OrdQty": str(quantity),
            "OrdPrc": str(price),
            "OrdCndiTpCode": "0",
        })
        try:
            response = await self._api.query(tr_code, request)
            rsp_cd = response.body.get("rsp_cd", "")
            is_success = rsp_cd.startswith("00")
            order_id = ""
            if is_success:
                parsed = tr.parse_response(response.body)
                outblock2 = parsed.get("CSPAT00701OutBlock2", {})
                order_id = str(outblock2.get("OrdNo", ""))
            return OrderResponse(is_success=is_success, order_id=order_id, message=response.body.get("rsp_msg", ""))
        except APIRequestError as e:
            return OrderResponse(is_success=False, order_id="", message=str(e))

    async def cancel_order(self, org_order_no: str, symbol: str, quantity: int) -> OrderResponse:
        tr_code = "CSPAT00801"
        tr = self._repo.get(tr_code)
        if tr is None:
            return OrderResponse(is_success=False, order_id="", message=f"TR '{tr_code}' not in spec")
        request = tr.build_request({
            "OrgOrdNo": org_order_no,
            "IsuNo": f"A{symbol}",
            "OrdQty": str(quantity),
        })
        try:
            response = await self._api.query(tr_code, request)
            rsp_cd = response.body.get("rsp_cd", "")
            is_success = rsp_cd.startswith("00")
            return OrderResponse(is_success=is_success, order_id="", message=response.body.get("rsp_msg", ""))
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

    async def get_server_time(self) -> str:
        tr = self._repo["t0167"]
        request = tr.build_request({"id": ""})
        try:
            response = await self._api.query(tr.code, request)
            rsp_cd = response.body.get("rsp_cd", "")
            if not rsp_cd.startswith("00"):
                raise APIRequestError(response.body.get("rsp_msg", ""), rsp_cd=rsp_cd, tr_code=tr.code)
            parsed = tr.parse_response(response.body)
            data = parsed.get("t0167OutBlock", {})
            if data and data.get("dt") and data.get("time"):
                date_str = data["dt"]
                time_str = data["time"]
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
            raise ValueError("server time data missing")
        except (APIRequestError, ValueError) as e:
            raise ConnectionError(f"get_server_time failed: {e}") from e

    async def get_historical_data(self, symbol: str, period: str, start_date: str = "", count: int = 100) -> list[HistoricalPrice]:
        period_map = {"day": 1, "week": 2, "month": 3}
        if period.lower() not in period_map:
            raise ValueError("period must be 'day', 'week', or 'month'")
        tr = self._repo["t1305"]
        req_date = start_date or datetime.now().strftime("%Y%m%d")
        request = tr.build_request({
            "shcode": symbol,
            "dwmcode": str(period_map[period.lower()]),
            "date": req_date,
            "idx": 0,
            "cnt": str(min(count, 500)),
        })
        all_prices = []
        try:
            data_block = tr.continuation.data_block if tr.continuation else "t1305OutBlock1"
            async for item_dict in self._api.continuous_query(tr.code, request, spec=tr):
                all_prices.append(HistoricalPrice.model_validate(item_dict))
                if len(all_prices) >= count:
                    break
            return all_prices
        except APIRequestError as e:
            if "APBK0042" in str(e):
                return []
            raise ConnectionError(f"get_historical_data failed ({symbol}): {e}") from e

    async def get_managed_stocks(self) -> set[str]:
        tr = self._repo["t1404"]
        request = tr.build_request({
            "gubun": "0",
            "jongchk": "1",
            "cts_shcode": "",
            "cts_date": "",
            "cts_time": "",
        })
        managed_codes = set()
        try:
            async for item_dict in self._api.continuous_query(tr.code, request, spec=tr):
                shcode = item_dict.get("shcode", "")
                if shcode:
                    managed_codes.add(shcode)
            return managed_codes
        except APIRequestError as e:
            print(f"Warning: get_managed_stocks failed: {e}")
            return set()
