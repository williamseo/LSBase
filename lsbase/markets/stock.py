# lsbase/markets/stock.py

import asyncio
from ..core.base import MarketBase
from ..core.enum import OrderSide, OrderType, RealtimeType
from ..core.models import OrderResult, Balance

class StockMarket(MarketBase):
    async def get_quote(self, symbol: str) -> dict:
        """국내 주식 현재가를 조회합니다."""
        tr_code = "t1102"
        params = {"t1102InBlock": {"shcode": symbol}}
        
        response = await self._api.query(tr_code, params)
        
        if response and response.body.get("rsp_cd") == "00000":
            data = response.body.get("t1102OutBlock")
            return {
                "symbol_name": data.get("hname"),
                "current_price": float(data.get("price")),
                "volume": int(data.get("volume")),
            }
        else:
            api_client = getattr(self._api, '_client', None)
            last_message = getattr(api_client, 'last_message', "알 수 없는 오류") if api_client else "API 클라이언트 없음"
            msg = response.body.get("rsp_msg") if response and response.body else f"API 요청 실패 ({last_message})"
            raise ConnectionError(f"시세 조회 실패: {msg}")

    # --- 아래는 향후 구현을 위한 플레이스홀더 ---
    async def place_order(self, symbol: str, quantity: int, price: int, side: OrderSide, order_type: OrderType) -> OrderResult:
        print("place_order가 호출되었으나 아직 구현되지 않았습니다.")
        pass

    async def modify_order(self, org_order_no: str, symbol: str, quantity: int, price: int) -> OrderResult:
        print("modify_order가 호출되었으나 아직 구현되지 않았습니다.")
        pass

    async def cancel_order(self, org_order_no: str, symbol: str, quantity: int) -> OrderResult:
        print("cancel_order가 호출되었으나 아직 구현되지 않았습니다.")
        pass

    async def get_account_balance(self) -> Balance:
        print("get_account_balance가 호출되었으나 아직 구현되지 않았습니다.")
        pass
    
    async def subscribe_realtime(self, symbol: str, data_type: RealtimeType):
        print("subscribe_realtime가 호출되었으나 아직 구현되지 않았습니다.")
        pass

    async def get_top_market_cap_stocks(self, market_type: str, limit: int = None) -> list[dict]:
        """
        [연속 조회 지원] 시가총액 상위 종목을 조회합니다.

        :param market_type: "KOSPI" 또는 "KOSDAQ"
        :param limit: 조회할 최대 종목 수. None이면 전체를 조회합니다.
        :return: 종목 정보 딕셔너리의 리스트
        """
        if market_type.upper() == "KOSPI":
            upcode = "001"
        elif market_type.upper() == "KOSDAQ":
            upcode = "301"
        else:
            raise ValueError("market_type은 'KOSPI' 또는 'KOSDAQ'이어야 합니다.")

        all_stocks = []
        tr_code = "t1444"
        
        page_idx = 0
        page_size = 50
        tr_cont = "N"

        print(f"\n{market_type} 시가총액 상위 종목 조회를 시작합니다 (최대: {limit or '전체'})...")

        while True:
            offset = page_idx * page_size
            
            params = {"t1444InBlock": {"upcode": upcode, "idx": offset}}
            
            response = await self._api.query(tr_code, params, tr_cont=tr_cont, tr_cont_key=str(offset))
            
            if not response or response.body.get("rsp_cd") != "00000":
                api_client = getattr(self._api, '_client', None)
                last_message = getattr(api_client, 'last_message', "알 수 없는 오류") if api_client else "API 클라이언트 없음"
                msg = response.body.get("rsp_msg") if response and response.body else f"API 요청 실패 ({last_message})"
                print(f"조회 중 오류 발생: {msg}")
                break

            batch = response.body.get("t1444OutBlock1", [])
            if not batch:
                break
                
            all_stocks.extend(batch)
            print(f"현재까지 {len(all_stocks)}개 종목 수집 완료...")

            if limit is not None and len(all_stocks) >= limit:
                break

            if response.tr_cont != "Y":
                break
            
            tr_cont = "Y"
            page_idx += 1
            await asyncio.sleep(0.5)
        
        if limit is not None:
            all_stocks = all_stocks[:limit]
            
        print(f"총 {len(all_stocks)}개의 {market_type} 종목 조회를 완료했습니다.")
        
        results = []
        for i, item in enumerate(all_stocks):
            results.append({
                "rank": i + 1,
                "name": item.get("hname"),
                "code": item.get("shcode"),
                "price": int(item.get("price", 0)),
                "market_cap_in_b_krw": int(item.get("total", 0)) 
            })
            
        return results
