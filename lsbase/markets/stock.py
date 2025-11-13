# lsbase/markets/stock.py

from ..core.base import MarketBase
from ..core.enum import OrderSide, OrderType, RealtimeType
from ..core.models import (
    OrderResponse, AccountBalanceSummary, Quote, MarketCapStock, HistoricalPrice
)
from ..core.exceptions import APIRequestError
from ..tr_adapter import TrCodeAdapter

from .. import generated_models as gen_models # 1. 자동 생성 모델 임포트
from pydantic import ValidationError
from datetime import datetime

class StockMarket(MarketBase):
    def __init__(self, api, spec: TrCodeAdapter, account_no, account_pw):
        super().__init__(api, account_no=account_no, account_pw=account_pw)
        self._spec = spec # spec 객체를 멤버 변수로 저장

    async def get_quote(self, symbol: str) -> Quote:
        """종목 현재가 시세(t1102)를 조회합니다."""
        tr = self._spec.주식.주식_시세.주식현재가_시세조회
        
        # 2. 자동 생성된 요청 모델을 사용하여 요청 데이터를 구성합니다.
        #    t1102는 InBlock이 하나뿐이므로 간단합니다.
        in_block = gen_models.T1102InBlock(shcode=symbol)
        request_model = gen_models.T1102Request(t1102InBlock=in_block)
        
        try:
            # 3. 모델을 딕셔너리로 변환하여 API를 호출합니다.
            response = await self._api.query(tr.code, request_model.model_dump())
            
            # 4. 응답 본문을 자동 생성된 응답 모델로 파싱(검증)합니다.
            parsed_response = gen_models.T1102Response.model_validate(response.body)
            data = parsed_response.t1102OutBlock
            
            if not data:
                raise ValueError("t1102 응답에서 OutBlock 데이터를 찾을 수 없습니다.")

            # 5. 최종적으로 사용자에게는 기존과 동일한 'Quote' 모델로 변환하여 반환합니다.
            #    이렇게 하면 라이브러리 내부 구현이 바뀌어도 사용자 코드는 영향을 받지 않습니다.
            return Quote.model_validate(data.model_dump())

        except (APIRequestError, ValueError, AttributeError) as e:
            # Pydantic 유효성 검사 실패(AttributeError) 등 다양한 예외를 포괄적으로 처리
            raise ConnectionError(f"시세 조회 실패 ({symbol}): {e}") from e

    async def place_order(self, symbol: str, quantity: int, price: int, side: OrderSide, order_type: OrderType) -> OrderResponse:
        """현물 주문(CSPAT00601)을 실행합니다."""
        tr = self._spec.주식.주식_주문.현물주문

        # 1. 자동 생성된 요청 모델을 사용하여 요청 데이터를 구성합니다.
        in_block = gen_models.Cspat00601InBlock1(
            IsuNo=f"A{symbol}",         # 종목번호 (API 규격: 'A' + 종목코드)
            OrdQty=quantity,           # 주문수량
            OrdPrc=price,              # 주문가격
            BnsTpCode="2" if side == OrderSide.BUY else "1",          # 매매구분 (2: 매수, 1: 매도)
            OrdprcPtnCode="03" if order_type == OrderType.MARKET else "00", # 호가유형 (00: 지정가, 03: 시장가)
            MgntrnCode="000",          # 신용거래코드 (000: 보통)
            LoanDt="",                 # 대출일 (공백)
            OrdCndiTpCode="0",         # 주문조건구분 (0: 없음)
            MbrNo="NXT"
        )
        request_model = gen_models.Cspat00601Request(CSPAT00601InBlock1=in_block)

        try:
            # 2. 모델을 딕셔너리로 변환하여 API를 호출합니다.
            response = await self._api.query(tr.code, request_model.model_dump(exclude_none=True))
            
            # 3. 응답 본문을 자동 생성된 응답 모델로 파싱(검증)합니다.
            parsed_response = gen_models.Cspat00601Response.model_validate(response.body)

            is_success = parsed_response.rsp_cd.startswith("00")
            order_id = ""
            
            # 4. 타입-안전하게 속성에 접근하여 주문번호를 가져옵니다.
            if is_success and parsed_response.CSPAT00601OutBlock2:
                order_id = str(parsed_response.CSPAT00601OutBlock2.OrdNo)

            return OrderResponse(
                is_success=is_success,
                order_id=order_id,
                message=parsed_response.rsp_msg
            )

        except APIRequestError as e:
            # API 레벨에서 발생한 오류 처리
            return OrderResponse(is_success=False, order_id="", message=str(e))
        except (ValueError, AttributeError) as e:
            # Pydantic 모델 파싱 실패 등 데이터 구조 문제 처리
            return OrderResponse(is_success=False, order_id="", message=f"주문 응답 처리 실패: {e}")

    async def get_account_balance(self) -> AccountBalanceSummary:
        """현물계좌 예수금/주문가능금액/총평가(CSPAQ12200)를 조회합니다."""
        tr = self._spec.주식.주식_계좌.현물계좌예수금_주문가능금액_총평가_조회

        in_block = gen_models.Cspaq12200InBlock1(
            RecCnt=0,
            MgmtBrnNo="",    
            BalCreTp="0"
        )
        request_model = gen_models.Cspaq12200Request(CSPAQ12200InBlock1=in_block)

        try:
            response = await self._api.query(tr.code, request_model.model_dump(exclude_none=True))
            parsed_response = gen_models.Cspaq12200Response.model_validate(response.body)

            # ★★★★★ 여기가 수정된 부분입니다 ★★★★★
            # CSPAQ12200OutBlock2가 리스트인지 단일 객체인지 확인하고 처리합니다.
            out_block_data = parsed_response.CSPAQ12200OutBlock2
            
            if out_block_data:
                # 리스트면 첫 번째 항목을, 단일 객체면 그 자체를 사용합니다.
                account_data = out_block_data[0] if isinstance(out_block_data, list) else out_block_data
                return AccountBalanceSummary.model_validate(account_data.model_dump())
            
            raise ValueError("계좌 잔고 데이터(OutBlock2)가 없습니다.")
        except (APIRequestError, ValidationError, ValueError, AttributeError, IndexError) as e:
            raise ConnectionError(f"계좌 잔고 조회 실패: {e}") from e

    async def get_top_market_cap_stocks(self, market_type: str, limit: int = None) -> list[MarketCapStock]:
        """시가총액 상위(t1444) 종목 목록을 조회합니다."""
        if market_type.upper() not in ["KOSPI", "KOSDAQ"]:
            raise ValueError("market_type은 'KOSPI' 또는 'KOSDAQ'이어야 합니다.")
        
        tr = self._spec.주식.주식_상위종목.시가총액상위
        upcode = "001" if market_type.upper() == "KOSPI" else "301"

        # 1. 자동 생성된 요청 모델을 사용하여 요청 데이터를 구성합니다.
        in_block = gen_models.T1444InBlock(upcode=upcode, idx=0) # idx는 연속 조회를 위해 int 사용
        request_model = gen_models.T1444Request(t1444InBlock=in_block)
        
        all_stocks = []
        rank = 1
        
        try:
            # 2. continuous_query에 모델을 딕셔너리로 변환하여 전달합니다.
            async for item_dict in self._api.continuous_query(tr.code, request_model.model_dump()):
                
                # 3. 반환된 딕셔너리(item_dict)를 자동 생성된 Item 모델로 파싱(검증)합니다.
                item = gen_models.T1444OutBlock1Item.model_validate(item_dict)
                
                # 4. 타입-안전하게 속성에 접근하여 데이터를 추출하고 최종 모델로 변환합니다.
                stock_info = MarketCapStock(
                    rank=rank,
                    name=item.hname,
                    code=item.shcode,
                    price=item.price,
                    market_cap_in_b_krw=item.total # 'total' 필드가 시가총액(백만원 단위)
                )
                all_stocks.append(stock_info)
                
                if limit is not None and len(all_stocks) >= limit:
                    break
                rank += 1
                
            return all_stocks
        except (APIRequestError, ValueError, AttributeError) as e:
            raise ConnectionError(f"시가총액 상위 종목 조회 실패: {e}") from e

    async def modify_order(self, org_order_no: str, symbol: str, quantity: int, price: int) -> OrderResponse:
        """현물 주문 정정(CSPAT00701)을 실행합니다."""
        tr_code = "CSPAT00701" # TrCodeAdapter에 아직 없을 수 있으므로 직접 지정

        in_block = gen_models.Cspat00701InBlock1(
            OrgOrdNo=int(org_order_no), # 원주문번호는 int 타입
            IsuNo=f"A{symbol}",
            OrdprcPtnCode="00",        # 지정가
            OrdQty=quantity,
            OrdPrc=price,
            OrdCndiTpCode="0"
        )
        request_model = gen_models.Cspat00701Request(CSPAT00701InBlock1=in_block)

        try:
            response = await self._api.query(tr_code, request_model.model_dump(exclude_none=True))
            parsed_response = gen_models.Cspat00701Response.model_validate(response.body)
            is_success = parsed_response.rsp_cd.startswith("00")
            order_id = ""
            if is_success and parsed_response.CSPAT00701OutBlock2:
                order_id = str(parsed_response.CSPAT00701OutBlock2.OrdNo)
            return OrderResponse(
                is_success=is_success, order_id=order_id, message=parsed_response.rsp_msg
            )
        except (APIRequestError, ValidationError, ValueError, AttributeError) as e:
            return OrderResponse(is_success=False, order_id="", message=f"주문 정정 처리 실패: {e}")

    async def cancel_order(self, org_order_no: str, symbol: str, quantity: int) -> OrderResponse:
        """현물 주문 취소(CSPAT00801)를 실행합니다."""
        tr_code = "CSPAT00801"

        in_block = gen_models.Cspat00801InBlock1(
            OrgOrdNo=int(org_order_no),
            IsuNo=f"A{symbol}",
            OrdQty=quantity
        )
        request_model = gen_models.Cspat00801Request(CSPAT00801InBlock1=in_block)

        try:
            response = await self._api.query(tr_code, request_model.model_dump(exclude_none=True))
            parsed_response = gen_models.Cspat00801Response.model_validate(response.body)
            is_success = parsed_response.rsp_cd.startswith("00")
            # 취소 주문은 보통 새로 발급되는 주문번호가 중요하지 않으므로 order_id는 비워둠
            return OrderResponse(
                is_success=is_success, order_id="", message=parsed_response.rsp_msg
            )
        except (APIRequestError, ValidationError, ValueError, AttributeError) as e:
            return OrderResponse(is_success=False, order_id="", message=f"주문 취소 처리 실패: {e}")

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
        """서버의 현재 시간(t0167)을 조회합니다."""
        tr = self._spec.기타.기타_시간조회.서버시간조회

        # t0167은 InBlock이 있지만 특별한 입력값이 필요 없음
        in_block = gen_models.T0167InBlock(id="")
        request_model = gen_models.T0167Request(t0167InBlock=in_block)

        try:
            response = await self._api.query(tr.code, request_model.model_dump())
            parsed_response = gen_models.T0167Response.model_validate(response.body)
            data = parsed_response.t0167OutBlock

            if data and data.dt and data.time:
                date_str = data.dt       # YYYYMMDD
                time_str = data.time     # HHMMSSssssss

                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"

            raise ValueError("서버 시간 응답 데이터가 없습니다.")
        except (APIRequestError, ValidationError, ValueError, AttributeError) as e:
            raise ConnectionError(f"서버 시간 조회 실패: {e}") from e

    async def get_historical_data(self, symbol: str, period: str, start_date: str = "", count: int = 100) -> list[HistoricalPrice]:
        """
        기간별 주가(t1305) 데이터를 조회합니다. 연속 조회를 지원합니다.
        
        :param symbol: 종목코드 (e.g., "005930")
        :param period: 조회 기간 단위 ("day", "week", "month")
        :param start_date: 조회 시작일 (YYYYMMDD). 지정하지 않으면 최신 데이터부터 조회.
        :param count: 조회할 데이터의 최대 개수
        :return: HistoricalPrice 모델 객체의 리스트
        """
        period_map = {"day": 1, "week": 2, "month": 3}
        if period.lower() not in period_map:
            raise ValueError("period는 'day', 'week', 'month' 중 하나여야 합니다.")

        tr = self._spec.주식.주식_시세.기간별주가
        
        # start_date가 없으면 오늘 날짜로 설정
        request_date = start_date if start_date else datetime.now().strftime('%Y%m%d')

        in_block = gen_models.T1305InBlock(
            shcode=symbol,
            dwmcode=period_map[period.lower()],
            date=request_date,
            idx=0, # 연속 조회 시작 인덱스
            cnt=count if count <= 500 else 500 # API는 한번에 약 500~600개 반환
        )
        request_model = gen_models.T1305Request(t1305InBlock=in_block)

        all_prices = []
        try:
            async for item_dict in self._api.continuous_query(tr.code, request_model.model_dump()):
                # 자동 생성된 모델로 데이터 검증
                item = gen_models.T1305OutBlock1Item.model_validate(item_dict)
                # 사용자 친화적인 모델로 변환하여 추가
                all_prices.append(HistoricalPrice.model_validate(item.model_dump()))

                if len(all_prices) >= count:
                    break
            
            return all_prices
        except (APIRequestError, ValidationError, ValueError) as e:
            # 존재하지 않는 종목코드 등 API 레벨 오류는 빈 리스트를 반환하여 처리
            if "APBK0042" in str(e): # 입력값 오류 코드
                return []
            raise ConnectionError(f"기간별 주가 조회 실패 ({symbol}): {e}") from e

    async def get_managed_stocks(self) -> set[str]:
        """관리 종목(t1404) 목록을 조회합니다."""
        tr = self._spec.주식.주식_시세.관리_불성실_투자유의조회

        in_block = gen_models.T1404InBlock(
            gubun="0",       # 0: 전체
            jongchk="1",     # 1: 관리종목
            cts_shcode="",   # 연속 조회 키 (초기에는 공백)
            cts_date="",
            cts_time=""
        )
        request_model = gen_models.T1404Request(t1404InBlock=in_block)

        managed_codes = set()
        try:
            async for item_dict in self._api.continuous_query(tr.code, request_model.model_dump(exclude_none=True)):
                item = gen_models.T1404OutBlock1Item.model_validate(item_dict)
                if item.shcode:
                    managed_codes.add(item.shcode)
            return managed_codes
        except (APIRequestError, ValidationError, ValueError, AttributeError) as e:
            print(f"경고: 관리 종목 조회에 실패했습니다. {e}")
            return set() # 오류가 발생해도 비어있는 set을 반환
