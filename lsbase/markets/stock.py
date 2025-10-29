# lsbase/markets/stock.py

from ..core.base import MarketBase
from ..core.enum import OrderSide, OrderType, RealtimeType
from ..core.models import (
    OrderResponse, AccountBalanceSummary, Quote, MarketCapStock,
    CSPAT00601InBlock, CSPAQ12200InBlock
)
from ..core.exceptions import APIRequestError
from ..tr_adapter import TrCodeAdapter

class StockMarket(MarketBase):
    def __init__(self, api, spec: TrCodeAdapter, account_no, account_pw):
        super().__init__(api, account_no=account_no, account_pw=account_pw)
        self._spec = spec # spec 객체를 멤버 변수로 저장

    async def get_quote(self, symbol: str) -> Quote:
        tr = self._spec.주식.주식_시세.주식현재가_시세조회
        
        # 요청 템플릿을 사용해 파라미터 구성
        params = tr.get_request_template()
        params['t1102InBlock']['shcode'] = symbol
        params['t1102InBlock']['exchgubun'] = "K"
        
        try:
            response = await self._api.query(tr.code, params)
            data = response.body.get("t1102OutBlock")
            return Quote.model_validate(data)
        except APIRequestError as e:
            raise ConnectionError(f"시세 조회 실패 ({symbol}): {e}") from e

    async def place_order(self, symbol: str, quantity: int, price: int, side: OrderSide, order_type: OrderType) -> OrderResponse:
        tr = self._spec.주식.주식_주문.현물주문
        
        # Pydantic 모델 대신 요청 템플릿 사용 (혹은 둘 다 활용 가능)
        params = tr.get_request_template()
        in_block = params[f'{tr.code}InBlock']
        
        in_block['IsuNo'] = f"A{symbol}" # 실제 API 규격에 맞게 'A' 접두사 추가
        in_block['OrdQty'] = quantity
        in_block['OrdPrc'] = price
        in_block['BnsTpCode'] = "2" if side == OrderSide.BUY else "1"
        in_block['OrdprcPtnCode'] = "03" if order_type == OrderType.MARKET else "00"
        
        try:
            response = await self._api.query(tr.code, params)
            data = response.body.get(f"{tr.code}OutBlock")
            return OrderResponse(
                is_success=True,
                order_id=data.get("OrdNo"),
                message=response.body.get("rsp_msg", "주문 성공")
            )
        except APIRequestError as e:
            return OrderResponse(is_success=False, order_id="", message=str(e))

    async def get_account_balance(self) -> AccountBalanceSummary:
        tr = self._spec.주식.주식_계좌.현물계좌예수금_주문가능금액_총평가_조회
        
        params = tr.get_request_template()
        params[f'{tr.code}InBlock']['BalCreTp'] = "0"
        
        try:
            response = await self._api.query(tr.code, params)
            data_list = response.body.get(f"{tr.code}OutBlock")
            if data_list:
                return AccountBalanceSummary.model_validate(data_list[0])
            raise ValueError("계좌 잔고 데이터가 없습니다.")
        except APIRequestError as e:
            raise ConnectionError(f"계좌 잔고 조회 실패: {e}") from e

    async def get_top_market_cap_stocks(self, market_type: str, limit: int = None) -> list[MarketCapStock]:
        if market_type.upper() not in ["KOSPI", "KOSDAQ"]:
            raise ValueError("market_type은 'KOSPI' 또는 'KOSDAQ'이어야 합니다.")
        
        tr = self._spec.주식.주식_상위종목.시가총액상위
        upcode = "001" if market_type.upper() == "KOSPI" else "301"

        params = tr.get_request_template()
        params[f'{tr.code}InBlock']['upcode'] = upcode
        params[f'{tr.code}InBlock']['idx'] = 0

        all_stocks = []
        rank = 1
        
        async for item in self._api.continuous_query(tr.code, params):
            stock_info = {
                "rank": rank,
                "name": item.get("hname"),
                "code": item.get("shcode"),
                "price": int(item.get("price", 0)),
                "market_cap_in_b_krw": int(item.get("total", 0)) # 단위가 '백만원'이므로 억 단위 변환 필요
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

    async def subscribe_realtime(self, key: str, data_type: RealtimeType) -> bool:
        """
        지정된 타입의 실시간 데이터를 구독합니다. TrCodeAdapter를 사용합니다.
        
        :param key: 종목코드 또는 실시간 TR에 필요한 키 값 (JIF의 경우 "1", "2" 등)
        :param data_type: 구독할 데이터의 종류 (RealtimeType 열거형)
        :return: 구독 요청 성공 여부
        """
        tr_code = None
        
        # RealtimeType에 따라 TrCodeAdapter에서 적절한 TR 코드를 찾아옵니다.
        # ※ 참고: 아래 경로는 ls_openapi_specs.json 파일의 구조에 따라 달라질 수 있습니다.
        if data_type == RealtimeType.EXECUTION:
            tr_code = self._spec.주식.실시간_시세.주식체결.code # 예: "S3_"
        elif data_type == RealtimeType.HOGA:
            tr_code = self._spec.주식.실시간_시세.주식호가.code # 예: "H1_"
        elif data_type == RealtimeType.MARKET_STATUS:
            tr_code = self._spec.기타.기타_실시간_시세.장운영정보.code # "JIF"
        elif data_type == RealtimeType.NEWS_HEADLINE:
            tr_code = self._spec.기타.기타_실시간_시세.실시간뉴스제목패킷.code
        else:
            raise NotImplementedError(f"지원하지 않는 실시간 데이터 타입입니다: {data_type}")
            
        if not tr_code:
            raise ValueError(f"'{data_type.value}'에 해당하는 TR 코드를 찾을 수 없습니다.")

        print(f"구독 요청 -> TR: {tr_code}, Key: {key}")
        return await self._api.subscribe_realtime(tr_code, key)

    async def unsubscribe_realtime(self, key: str, data_type: RealtimeType) -> bool:
        """실시간 데이터 구독을 해제합니다."""
        # subscribe_realtime과 동일한 로직으로 TR 코드를 찾습니다.
        tr_code = None

        if data_type == RealtimeType.EXECUTION:
            tr_code = self._spec.주식.실시간_시세.주식체결.code
        elif data_type == RealtimeType.HOGA:
            tr_code = self._spec.주식.실시간_시세.주식호가.code
        elif data_type == RealtimeType.MARKET_STATUS:
            tr_code = self._spec.기타.기타_실시간_시세.장운영정보.code
        elif data_type == RealtimeType.NEWS_HEADLINE:
            tr_code = self._spec.기타.기타_실시간_시세.실시간뉴스제목패킷.code
        else:
            raise NotImplementedError(f"지원하지 않는 실시간 데이터 타입입니다: {data_type}")

        if not tr_code:
            raise ValueError(f"'{data_type.value}'에 해당하는 TR 코드를 찾을 수 없습니다.")

        print(f"구독 해제 요청 -> TR: {tr_code}, Key: {key}")
        return await self._api.unsubscribe_realtime(tr_code, key)

    async def get_server_time(self) -> str:
        """
        서버의 현재 시간을 조회합니다 (t0167).

        :return: "YYYY-MM-DD HH:MM:SS" 형식의 시간 문자열
        """
        # TrCodeAdapter를 사용하여 '서버시간조회' TR 명세를 가져옵니다.
        # ls_tr_overview.json 구조에 따라 경로를 지정합니다.
        tr = self._spec.기타.기타_시간조회.서버시간조회
        
        # t0167은 InBlock에 특별한 입력값이 필요 없으므로 템플릿을 그대로 사용합니다.
        params = tr.get_request_template()
        params['t0167InBlock']['id'] = ""
        
        try:
            response = await self._api.query(tr.code, params)
            data = response.body.get("t0167OutBlock")
            if data:
                date_str = data.get("dt", "--------")       # YYYYMMDD
                time_str = data.get("time", "------------") # HHMMSSssssss
                
                # 보기 좋은 형태로 포맷팅합니다.
                formatted_time = (
                    f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} "
                    f"{time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
                )
                return formatted_time
            
            raise ValueError("서버 시간 응답 데이터가 없습니다.")
        except APIRequestError as e:
            raise ConnectionError(f"서버 시간 조회 실패: {e}") from e

