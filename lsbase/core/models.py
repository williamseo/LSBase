# lsbase/core/models.py

from pydantic import BaseModel, Field
from typing import Optional

# --- API 응답 모델 ---

class OrderResponse(BaseModel):
    is_success: bool
    order_id: str
    message: str

class AccountBalanceSummary(BaseModel):
    cash: int = Field(alias="Dps", description="예수금")
    total_assets: int = Field(alias="DpsastTotamt", description="예탁자산총액")
    total_purchase_amount: int = Field(alias="PchsAmt", description="총매입금액")
    total_evaluation_amount: int = Field(alias="BalEvalAmt", description="잔고평가금액")
    profit_loss_rate: float = Field(alias="PnlRat", description="손익율")

class Quote(BaseModel):
    symbol_name: str = Field(alias="hname")
    current_price: float = Field(alias="price")
    volume: int

class MarketCapStock(BaseModel):
    rank: int
    name: str
    code: str
    price: int
    market_cap_in_b_krw: int


# --- 저수준(Low-level) API TR 모델 ---

# 현물주문 (CSPAT00601)
class CSPAT00601InBlock(BaseModel):
    IsuNo: str
    OrdQty: int
    OrdPrc: int
    BnsTpCode: str  # 1: 매도, 2: 매수
    OrdprcPtnCode: str # 00: 지정가, 03: 시장가

class CSPAT00601OutBlock(BaseModel):
    OrdNo: str
    OrdTime: str

# 현물계좌 예수금/주문가능금액 조회 (CSPAQ12200)
class CSPAQ12200InBlock(BaseModel):
    BalCreTp: str = "0"

class CSPAQ12200OutBlock(AccountBalanceSummary):
    # AccountBalanceSummary의 모든 필드를 상속받아 사용
    pass
