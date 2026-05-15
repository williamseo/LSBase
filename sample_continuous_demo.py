"""연속조회(ContinuationSpec) 데모 — t1444 시가총액상위

SpecRepository + TrSpec.continuation + continuous_query(spec=tr)의
전체 파이프라인을 보여줍니다.

실행:
  python sample_continuous_demo.py
"""
import asyncio
from lsbase import MarketClient


def fmt_price(v) -> str:
    v = int(v or 0)
    if v >= 10_000_000_000_000:
        return f"{v / 1_000_000_000_000:.2f}조"
    if v >= 100_000_000:
        return f"{v / 100_000_000:.0f}억"
    return f"{v:,}"


async def main():
    client = MarketClient(monitor_market_state=False)
    try:
        if not await client.connect():
            return

        # 1. TR 조회 — repo["t1444"]
        tr = client._repo["t1444"]
        print(f"TR: [{tr.code}] {tr.name}")
        print(f"분류: {tr.tr_class.value}, 연속조회 지원: {tr.continuation is not None}")

        if tr.continuation:
            c = tr.continuation
            print(f"데이터블록: {c.data_block}")
            print(f"연속키블록: {c.continuation_block}")
            print(f"연속키필드: {c.key_fields}")
            print(f"종료조건: {c.stop_condition.value}")
        print()

        # 2. 요청 파라미터
        params = tr.build_request({
            "upcode": "001",  # KOSPI
            "idx": 0,
        })
        print(f"요청: {params}")
        print()

        # 3. 연속조회 (spec=tr로 ContinuationSpec 자동 적용)
        print(f"{'순위':>4s} {'종목명':<16s} {'코드':<8s} {'현재가':>10s} {'시가총액':>12s} {'등락율':>8s}")
        print("-" * 62)

        page = 0
        count = 0
        async for item in client._api.continuous_query(tr.code, params, spec=tr):
            page += 1
            name = item.get("hname", "")
            code = item.get("shcode", "")
            price = int(item.get("price", 0) or 0)
            market_cap = int(item.get("total", 0) or 0)
            diff = float(item.get("diff", 0) or 0)
            arrow = "▲" if diff >= 0 else "▼"
            count += 1
            if count <= 20:
                print(f"  {count:3d}  {name:<16s} {code:<8s} {price:>10,} {fmt_price(market_cap):>12s} {arrow} {abs(diff):>6.2f}%")

        print(f"\n총 {count}개 종목 (연속조회 페이지: {page}회 요청)")

        # 4. 페이지 수 상세
        if tr.continuation:
            c = tr.continuation
            print(f"데이터블록: {c.data_block}")
            print(f"연속키블록: {c.continuation_block}")
            print(f"연속키필드: {c.key_fields}")

    except Exception as e:
        print(f"오류: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
