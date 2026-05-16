import asyncio
from lsbase import MarketClient

async def fetch_rankings(client, gubun: str, type1: str, label: str):
    tr = client._repo["t1442"]
    params = tr.build_request({
        "gubun": gubun, "type1": type1, "type2": "0", "type3": "0",
        "jc_num": 0, "sprice": 0, "eprice": 0, "volume": 0,
        "idx": 0, "jc_num2": 0,
    })
    results = []
    try:
        async for item in client._api.continuous_query(tr.code, params, spec=tr):
            results.append(item)
    except Exception as e:
        pass
    results.sort(key=lambda x: int(x.get("diff", 0) or 0), reverse=True)
    print(f"\n  [{label}] 총 {len(results)}개")
    print(f"  {'순위':>4s} {'종목명':<16s} {'코드':<8s} {'현재가':>10s} {'등락율':>8s} {'거래량':>12s}")
    print(f"  {'-'*62}")
    for rank, item in enumerate(results[:15], 1):
        name = item.get("hname", "")
        code = item.get("shcode", "")
        price = int(item.get("price", 0) or 0)
        diff = float(item.get("diff", 0) or 0)
        volume = int(item.get("volume", 0) or 0)
        arrow = "▲" if diff > 0 else "▼"
        print(f"  {rank:4d} {name:<16s} {code:<8s} {price:>10,} {arrow} {abs(diff):>6.2f}% {volume:>12,}")

async def main():
    client = MarketClient(monitor_market_state=False)
    try:
        if not await client.connect():
            return
        print("=== 신고가/신저가 종목 ===")
        await fetch_rankings(client, "0", "1", "신고가 (52주 최고가 돌파)")
        await fetch_rankings(client, "0", "2", "신저가 (52주 최저가)")
    except Exception as e:
        print(f"오류: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
