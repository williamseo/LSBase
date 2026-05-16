# LSBase - LS증권 비공식 차세대 비동기 API 프레임워크

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`LSBase`는 LS증권(구 이베스트투자증권) Open API를 Pythonic하게 사용할 수 있도록 설계된 비동기 프레임워크입니다.
`TrSpec` + `SpecRepository`를 기반으로 **타입 안정성, 자동 검증, 시장별 다형성**을 제공합니다.

## 주요 특징

- **`TrSpec` 명세 추상화** — 364개 TR을 Pydantic 모델로 관리, TR 코드로 즉시 조회
- **`build_request()` 자동 검증** — 필수 필드 체크 + 타입 변환 + 길이 검증
- **`ContinuationSpec` 선언적 연속조회** — heuristic 제거, 명세 기반 페이지네이션
- **시장별 다형성** — 주식/선물/해외주식/해외선물 동일 인터페이스
- **`Throttler` 속도 제한** — Token bucket 알고리즘으로 API 호출 제한 자동 준수
- **완전 비동기** — `asyncio` + `aiohttp` 기반
- **`generated_models.py` 불필요** — 1,547개 Pydantic 클래스 대신 경량 TrSpec

## 설치

```bash
git clone https://github.com/williamseo/LSBase.git
cd LSBase
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## 설정

`.env` 파일 생성:
```env
APP_KEY="발급받은_APP_KEY"
APP_SECRET="발급받은_APP_SECRET"
ACCOUNT_NO="계좌번호_8자리"
ACCOUNT_PASSWORD="계좌비밀번호"
```

## (최초 1회) TR 명세 생성

```bash
python lsbase/tools/generate_specs.py
```

`lsbase/_tr_specs.py`가 생성됩니다 (364개 TR).

## 빠른 시작

### 주식 현재가 조회

```python
import asyncio
from lsbase import MarketClient

async def main():
    client = MarketClient()
    await client.connect()

    quote = await client.stock.get_quote("005930")
    print(f"{quote.symbol_name}: {quote.current_price:,.0f}원")

    await client.disconnect()

asyncio.run(main())
```

### TR 코드로 직접 조회

```python
tr = client._repo["t1102"]
packet = tr.build_request({"shcode": "005930"})
response = await client._api.query("t1102", packet)
data = tr.parse_response(response.body)
```

### 연속조회 (자동 페이지네이션)

```python
tr = client._repo["t1444"]
async for item in client._api.continuous_query(tr.code, params, spec=tr):
    print(item["hname"], item["price"])
```

## 시장별 인터페이스

```python
client.stock.get_quote("005930")              # 주식
client.futures.get_quote("101P3000")           # 선물/옵션
client.overseas.get_quote("TSLA", "82")        # 해외주식
client.overseas_futures.get_quote("CL")        # 해외선물
```

## 샘플 목록

| 파일 | 설명 |
|------|------|
| `sample_get_price.py` | 주식 현재가 조회 |
| `sample_get_balance.py` | 계좌 잔고 조회 |
| `sample_get_top_stocks.py` | 시가총액 상위 조회 |
| `sample_place_order.py` | 지정가 주문 |
| `sample_high_value_stocks.py` | 거래대금 200억 이상 종목 |
| `sample_continuous_demo.py` | 연속조회 + ContinuationSpec 데모 |
| `sample_futures_quote.py` | 선물 현재가 |
| `sample_overseas_quote_simple.py` | 해외주식 현재가 |
| `sample_ofutures_quote.py` | 해외선물 현재가 |
| `sample_realtime_monitor.py` | 실시간 체결 모니터링 |
| `sample_foreign_trend.py` | 외인/기관 매매동향 |
| `sample_new_high_low.py` | 신고가/신저가 연속조회 |
| `sample_chart_nmin.py` | N분봉 차트 연속조회 |
| `full_order_cycle.py` | 주문 전체 사이클 |

## API 호출 속도 제한

기본 5회/초, burst 5. 설정 변경:

```python
client = MarketClient(api_call_rate=10.0, api_burst=10)
```

## TR 검색 도구

```bash
python searchtr.py t1102            # TR 상세 조회
python searchtr.py --search 현재가    # TR 검색
```

## 테스트

```bash
pip install pytest pytest-asyncio
python -m pytest tests/
```

## 프로젝트 구조

```
LSBase/
├── lsbase/
│   ├── core/
│   │   ├── spec_models.py     # TrSpec, FieldSpec, SpecRepository
│   │   ├── throttler.py       # API 호출 속도 제한
│   │   ├── models.py          # 고수층 응답 모델
│   │   ├── base.py            # MarketBase 추상 클래스
│   │   └── api_interface.py   # TradingAPI 인터페이스
│   ├── markets/
│   │   ├── stock.py           # StockMarket
│   │   ├── futures_options.py # FuturesOptionsMarket
│   │   ├── overseas_stock.py  # OverseasStockMarket
│   │   └── overseas_futures.py# OverseasFuturesMarket
│   ├── api_client/
│   │   └── ls_api.py          # LSTradingAPI (throttler 내장)
│   ├── openapi_client/        # OpenApi HTTP/WS 래퍼
│   ├── tools/
│   │   ├── generate_specs.py  # 명세 생성기
│   │   └── update_api_specs.py# API 스크레이퍼
│   └── _tr_specs.py           # (자동 생성) 364개 TR 명세
├── tests/
│   ├── test_spec_models.py    # TrSpec 단위 테스트
│   ├── test_throttler.py      # Throttler 테스트
│   └── test_samples.py        # 샘플 문법 검증
├── tools/
│   └── validate_spec.py       # 명세 대응 검증 도구
├── sample_*.py                # 사용 예제
└── docs/
    └── ROADMAP.md             # 개발 로드맵
```

## 라이선스

MIT
