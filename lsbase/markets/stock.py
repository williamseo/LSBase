# lsbase/markets/stock.py

from ..core.base import MarketBase
from ..core.enum import OrderSide, OrderType, RealtimeType
from ..core.models import (
    OrderResponse, AccountBalanceSummary, Quote, MarketCapStock,
    CSPAT00601InBlock, CSPAQ12200InBlock
)
from ..core.exceptions import APIRequestError

class StockMarket(MarketBase):
    async def get_quote(self, symbol: str) -> Quote:
        tr_code = "t1102"
        params = {"t1102InBlock": {"shcode": symbol}}
        try:
            response = await self._api.query(tr_code, params)
            data = response.body.get("t1102OutBlock")
            return Quote.model_validate(data)
        except APIRequestError as e:
            raise ConnectionError(f"시세 조회 실패 ({symbol}): {e}") from e

    async def place_order(self, symbol: str, quantity: int, price: int, side: OrderSide, order_type: OrderType) -> OrderResponse:
        tr_code = "CSPAT00601"
        in_block = CSPAT00601InBlock(
            IsuNo=f"A{symbol}",
            OrdQty=quantity,
            OrdPrc=price,
            BnsTpCode="2" if side == OrderSide.BUY else "1",
            OrdprcPtnCode="03" if order_type == OrderType.MARKET else "00"
        )
        params = {f"{tr_code}InBlock": in_block.model_dump()}
        try:
            response = await self._api.query(tr_code, params)
            data = response.body.get(f"{tr_code}OutBlock")
            return OrderResponse(
                is_success=True,
                order_id=data.get("OrdNo"),
                message=response.body.get("rsp_msg", "주문 성공")
            )
        except APIRequestError as e:
            return OrderResponse(is_success=False, order_id="", message=str(e))

    async def get_account_balance(self) -> AccountBalanceSummary:
        tr_code = "CSPAQ12200"
        params = {f"{tr_code}InBlock": CSPAQ12200InBlock().model_dump()}
        try:
            response = await self._api.query(tr_code, params)
            # OutBlock이 리스트 형태로 반환될 수 있음
            data_list = response.body.get(f"{tr_code}OutBlock")
            if data_list:
                return AccountBalanceSummary.model_validate(data_list[0])
            raise ValueError("계좌 잔고 데이터가 없습니다.")
        except APIRequestError as e:
            raise ConnectionError(f"계좌 잔고 조회 실패: {e}") from e

    async def get_top_market_cap_stocks(self, market_type: str, limit: int = None) -> list[MarketCapStock]:
        if market_type.upper() not in ["KOSPI", "KOSDAQ"]:
            raise ValueError("market_type은 'KOSPI' 또는 'KOSDAQ'이어야 합니다.")
        
        upcode = "001" if market_type.upper() == "KOSPI" else "301"
        tr_code = "t1444"
        params = {"t1444InBlock": {"upcode": upcode, "idx": 0}}

        all_stocks = []
        rank = 1
        
        async for item in self._api.continuous_query(tr_code, params):
            stock_info = {
                "rank": rank,
                "name": item.get("hname"),
                "code": item.get("shcode"),
                "price": int(item.get("price", 0)),
                "market_cap_in_b_krw": int(item.get("total", 0))
            }
            all_stocks.append(MarketCapStock.model_validate(stock_info))
            
            if limit is not None and len(all_stocks) >= limit:
                break
            rank += 1
            
        return all_stocks

    # --- 아래는 향후 구현을 위한 플레이스홀더 ---
    async def modify_order(self, org_order_no: str, symbol: str, quantity: int, price: int) -> OrderResponse:
        print("modify_order가 호출되었으나 아직 구현되지 않았습니다.")
        pass

    async def cancel_order(self, org_order_no: str, symbol: str, quantity: int) -> OrderResponse:
        print("cancel_order가 호출되었으나 아직 구현되지 않았습니다.")
        pass

    async def subscribe_realtime(self, symbol: str, data_type: RealtimeType):
        print("subscribe_realtime가 호출되었으나 아직 구현되지 않았습니다.")
        pass
