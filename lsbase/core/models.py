from dataclasses import dataclass

@dataclass
class OrderResult:
    is_success: bool
    order_id: str
    message: str

@dataclass
class Balance:
    cash: float
    total_assets: float
