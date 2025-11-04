# lsbase/core/models.py (수정된 버전)

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime

# --- API 응답 모델 (High-level) ---
# 이 모델들은 라이브러리 사용자와 직접 소통하는 고수준 추상화 모델이므로 유지합니다.

class OrderResponse(BaseModel):
    """주문 요청에 대한 표준 응답 모델"""
    is_success: bool
    order_id: str
    message: str

class AccountBalanceSummary(BaseModel):
    cash: int = Field(alias="Dps")
    orderable_amount: int = Field(alias="MnyOrdAbleAmt")
    total_assets: int = Field(alias="DpsastTotamt")
    total_purchase_amount: int = Field(alias="InvstOrgAmt", default=0)
    total_evaluation_amount: int = Field(alias="BalEvalAmt", default=0)
    profit_loss_amount: int = Field(alias="InvstPlAmt", default=0)
    profit_loss_rate: float = Field(alias="PnlRat", default=0.0)

class Quote(BaseModel):
    """단일 종목의 현재 시세를 나타내는 모델"""
    symbol_name: str = Field(alias="hname")
    current_price: float = Field(alias="price")
    volume: int = Field(alias="volume")

class MarketCapStock(BaseModel):
    """시가총액 상위 종목 정보를 담는 모델"""
    rank: int
    name: str
    code: str
    price: int
    market_cap_in_b_krw: int

class MarketStatus(str, Enum):
    """시장의 현재 운영 상태를 나타내는 열거형"""
    UNKNOWN = "UNKNOWN"               # 알 수 없음 (초기 상태)
    PRE_MARKET = "PRE_MARKET"         # 장전 동시호가 또는 프리마켓
    OPEN = "OPEN"                     # 정규장 진행 중
    POST_MARKET = "POST_MARKET"       # 장후 동시호가 또는 애프터마켓
    CLOSED = "CLOSED"                 # 장 마감
    DANILGA = "DANILGA"               # 시간외 단일가

class MarketState(BaseModel):
    """특정 시장의 상태 정보를 담는 모델"""
    market_name: str
    status: MarketStatus = MarketStatus.UNKNOWN
    last_updated: Optional[datetime] = None
    raw_jstatus_code: Optional[str] = None # 원본 상태 코드 저장
