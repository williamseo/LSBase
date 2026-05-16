import asyncio
from datetime import datetime, timedelta
from lsbase import MarketClient

STOCKS = ["005930", "000660", "207940", "005380", "068270", "035420", "051910", "006400"]
TODAY = datetime.now().strftime("%Y%m%d")

async def fetch_foreign_netbuy(client, code: str, gubun: str, date: str) -> dict:
    tr = client._repo["t1717"]
    params = tr.build_request({"shcode": code, "gubun": gubun, "fromdt": date, "todt": date})
    response = await client._api.query(tr.code, params)
    parsed = tr.parse_response(response.body)
    return parsed.get("t1717OutBlock", {})

async def main():
    client = MarketClient(monitor_market_state=False)
    try:
        if not await client.connect():
            return
        print(f"=== 외인/기관 매매동향 (기준: {TODAY}) ===\n")
        for label, gubun in [("외국인", "0"), ("기관", "1")]:
            print(f"  [{label} 순매수]")
            print(f"  {'종목명':<16s} {'코드':<8s} {'순매수':>12s} {'현재가':>10s} {'등락율':>8s}")
            print(f"  {'-'*56}")
            results = []
            for code in STOCKS:
                data = await fetch_foreign_netbuy(client, code, gubun, TODAY)
                nets = int(data.get("nets", 0) or 0)
                if nets != 0:
                    name = data.get("hname", "")
                    price = int(data.get("price", 0) or 0)
                    diff = float(data.get("diff", 0) or 0)
                    results.append((nets, name, code, price, diff))
            results.sort(key=lambda x: -x[0])
            for nets, name, code, price, diff in results:
                arrow = "▲" if diff > 0 else "▼"
                print(f"  {name:<16s} {code:<8s} {nets:>12,} {price:>10,} {arrow} {abs(diff):>6.2f}%")
            print()
    except Exception as e:
        print(f"오류: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
