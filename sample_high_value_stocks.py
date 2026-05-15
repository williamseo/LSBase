import asyncio
from datetime import datetime
from lsbase import MarketClient

# value 단위: 백만원 (1 = 1,000,000원)
MIN_VALUE = 20_000  # 거래대금 200억 이상 (20,000백만원)


def format_value(v: int) -> str:
    v_won = v * 1_000_000
    if v_won >= 1_000_000_000_000:
        return f"{v_won / 1_000_000_000_000:.2f}조"
    if v_won >= 100_000_000:
        return f"{v_won / 100_000_000:.0f}억"
    return f"{v_won:,}원"


async def main():
    client = MarketClient(monitor_market_state=False)
    try:
        if not await client.connect():
            print("API 서버 연결 실패")
            return

        tr = client._repo["t1463"]
        print(f"=== [{tr.code}] {tr.name} ===")
        print(f"조건: 거래대금 {format_value(MIN_VALUE)} 이상")
        print()

        params = tr.build_request({
            "gubun": "1",
            "jnilgubun": "1",
            "jc_num": 0,
            "sprice": 0,
            "eprice": 0,
            "volume": 0,
            "idx": 0,
            "jc_num2": 0,
        })

        results = []
        try:
            async for item in client._api.continuous_query(tr.code, params):
                value = int(item.get("value", 0))
                if value >= MIN_VALUE:
                    results.append(item)
        except Exception as e:
            print(f"  연속조회 중 오류 (일부 데이터만 표시): {e}")

        results.sort(key=lambda x: int(x.get("value", 0)), reverse=True)

        print(f"\n  {'순위':>4s} {'종목명':<16s} {'코드':<8s} {'현재가':>10s} {'거래대금':>14s} {'거래량':>12s} {'등락율':>8s}")
        print(f"  {'-'*74}")
        for rank, item in enumerate(results[:30], 1):
            name = item.get("hname", "")
            code = item.get("shcode", "")
            price = int(item.get("price", 0))
            value = int(item.get("value", 0))
            volume = int(item.get("volume", 0))
            diff = float(item.get("diff", 0))
            print(f"  {rank:4d} {name:<16s} {code:<8s} {price:>10,} {format_value(value):>14s} {volume:>12,} {diff:>7.2f}%")

        total = len(results)
        print(f"\n  총 {total}개 종목 (거래대금 {format_value(MIN_VALUE)} 이상)")
        if total > 30:
            print(f"  (상위 30개만 표시)")

    except Exception as e:
        print(f"오류: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
