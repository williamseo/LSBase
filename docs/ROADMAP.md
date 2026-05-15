# LSBase 로드맵

> LS증권 차세대 비동기 API 프레임워크

## 상태 요약

| 레이어 | 상태 | 비고 |
|--------|------|------|
| OpenApi (HTTP/WS raw) | ✅ 안정 | 수정 불필요 |
| TradingAPI / LSTradingAPI | ✅ 안정 | 수정 불필요 |
| `TrSpec` + `SpecRepository` | ✅ 완료 | v1.0 |
| `stock.py` 마이그레이션 | ✅ 완료 | TrCodeAdapter → SpecRepository |
| 샘플 전환 | ✅ 완료 | 13개 샘플 |

---

## Phase 1 — 시장 다형성 (Market Polymorphism)

**목표**: `MarketBase`를 상속받는 시장별 구현체를 추가하여 모든 시장을 동일한 인터페이스로 사용

```
client.stock.get_quote("005930")
client.futures.get_quote("101P3000")
client.overseas.get_quote("TSLA")
client.futures_options.get_quote("...")
```

### 작업 항목

| 작업 | 설명 | 예상 시간 | 우선순위 |
|------|------|-----------|---------|
| `_tr_specs.py` 시장 분류 검증 | 364개 TR의 `market` 필드가 정확한지 확인 | 1일 | P0 |
| `FuturesOptionsMarket` 구현 | 선물/옵션 시세, 주문, 계좌, 실시간 | 3일 | P0 |
| `OverseasStockMarket` 구현 | 해외주식 시세, 주문, 계좌 | 2일 | P0 |
| `OverseasFuturesMarket` 구현 | 해외선물 시세, 주문, 계좌 | 2일 | P1 |
| `MarketClient` 통합 | `client.futures`, `client.overseas` 등 속성 노출 | 1일 | P0 |
| 시장별 샘플 | 각 시장별 샘플 코드 2~3개 | 2일 | P1 |

### 핵심 설계

각 Market 클래스는 `SpecRepository`에서 TR 코드를 조회하고 `build_request()`로 패킷을 조립:

```python
class FuturesOptionsMarket(MarketBase):
    async def get_quote(self, symbol: str) -> FuturesQuote:
        tr = self._repo["t2101"]  # 선물/옵션현재가
        params = tr.build_request({"shcode": symbol})
        response = await self._api.query(tr.code, params)
        data = tr.parse_response(response.body)
        return FuturesQuote.model_validate(data.get("t2101OutBlock", {}))
```

---

## Phase 2 — 연속조회 리팩토링

**목표**: `ls_api.py`의 67줄 heuristic → `ContinuationSpec` 기반 선언적 처리

### 현재 문제

```python
# ls_api.py continuous_query() — 67줄 heuristic
out_block_key = f"{tr_code}OutBlock1"              # 하드코딩된 블록명 규칙
continuation_out_block_key = f"{tr_code}OutBlock"   # OutBlock/OutBlock1 구분
# InBlock 키 find() + OutBlock/InBlock 공통 필드 매칭
```

### 해결 방안

```python
# future ls_api.py
async def continuous_query(self, tr_code, params, spec: TrSpec):
    cont = spec.continuation
    while True:
        response = await self.query(...)
        for item in response.body.get(cont.data_block, []):
            yield item
        if response.tr_cont != "Y":
            break
        params, cont = cont.extract_next_params(response.body, params, in_block_key)
```

### 작업 항목

| 작업 | 설명 | 예상 시간 |
|------|------|----------|
| `LSTradingAPI.continuous_query()` 리팩토링 | `ContinuationSpec` 사용 | 1일 |
| 48개 연속조회 TR 검증 | 각 TR의 continuation 정확성 확인 | 1일 |
| `StockMarket` 연속조회 메서드 업데이트 | `get_top_market_cap_stocks` 등 | 0.5일 |

---

## Phase 3 — 검증 레이어 (Validation)

**목표**: `build_request()`와 `parse_response()`가 strict 모드에서 Pydantic 수준의 검증 제공

| 작업 | 설명 | 예상 시간 |
|------|------|----------|
| `strict=True` 모드 테스트 | 모든 샘플에서 strict 모드 검증 | 1일 |
| 필드 길이/타입 불일치 데이터 분석 | 실제 API 응답과 명세 차이 분석 | 1일 |
| `parse_response()`에 unknown 필드 수집 | API가 문서에 없는 필드를 내려주는 경우 로깅 | 0.5일 |

---

## Phase 4 — 테스트

| 작업 | 설명 | 예상 시간 |
|------|------|----------|
| `test_spec_models.py` | `TrSpec.build_request()` / `parse_response()` / `_coerce()` 단위 테스트 | 1일 |
| `test_sample_syntax.py` | 모든 샘플 문법 검증 CI | 0.5일 |
| `test_continuation.py` | `ContinuationSpec.extract_next_params()` 로직 테스트 | 0.5일 |
| `test_repository.py` | `SpecRepository` 조회/검색/by_market 테스트 | 0.5일 |

---

## Phase 5 — 문서화

| 작업 | 설명 | 예상 시간 |
|------|------|----------|
| README.md 업데이트 | 새 아키텍처, SpecRepository 사용법 | 1일 |
| API 레퍼런스 | `TrSpec`, `FieldSpec`, `SpecRepository` 메서드 문서 | 1일 |
| 마이그레이션 가이드 | `TrCodeAdapter` → `SpecRepository` 전환 방법 | 0.5일 |

---

## Phase 6 — 저장소 최적화 (선택)

| 작업 | 설명 | 예상 시간 |
|------|------|----------|
| SQLite 저장소 옵션 | `SpecRepository` + SQLite 구현 (`generate_specs_db.py`) | 1일 |
| `_tr_specs.py` 크기 최적화 | 필드 포맷 tuple 전환으로 1.9MB → ~500KB | 0.5일 |
| `tr_adapter.py` 제거 | deprecation 기간 이후 완전 삭제 | 0.5일 |

---

## Phase 7 — 고도화 (장기)

| 작업 | 설명 |
|------|------|
| `Symbol` 타입 | `"005930"` 대신 `Symbol("005930", market=Market.STOCK)` | 
| 자동 재연결 | WebSocket 끊겼을 때 자동 재구독 |
| 레이트 리밋 | API 호출 제한 자동 관리 (호출 건수 초과 시 대기 후 재시도) |
| 캐싱 | `SpecRepository` LRU 캐시로 자주 쓰는 TR만 메모리에 유지 |
| CLI 도구 | `lsbase search t1102`, `lsbase quote 005930` 등 커맨드라인 |

---

## 일정 (예상)

```
Phase 1: 시장 다형성       ████████████░░░░░░  2주
Phase 2: 연속조회 리팩토링    ██████░░░░░░░░░░░░  1주
Phase 3: 검증 레이어        ████░░░░░░░░░░░░░░  0.5주
Phase 4: 테스트             ██████░░░░░░░░░░░░  1주
Phase 5: 문서화             ██████░░░░░░░░░░░░  1주
Phase 6: 저장소 최적화       ████░░░░░░░░░░░░░░  선택
Phase 7: 고도화             ████████████████████  장기
```

> `TrCodeAdapter`는 현재 `lsbase/tr_adapter.py`에 deprecated 경고와 함께 유지 중.
> Phase 6 이후 완전 제거 예정.
