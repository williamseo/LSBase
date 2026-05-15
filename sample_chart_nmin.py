import asyncio
from datetime import datetime, timedelta
from lsbase import MarketClient

def print_chart(title: str, data: list[dict], max_rows: int = 20):
    print(f"\n=== {title} ===")
    print(f"{'날짜':<10s} {'시간':<8s} {'시가':>10s} {'고가':>10s} {'저가':>10s} {'종가':>10s} {'거래량':>12s}")
    print("-" * 72)
    for item in data[:max_rows]:
        date = item.get("date", "")
        time = item.get("time", "")
        open_p = int(item.get("open", 0) or 0)
        high = int(item.get("high", 0) or 0)
        low = int(item.get("low", 0) or 0)
        close = int(item.get("close", 0) or 0)
        volume = int(item.get("volume", 0) or 0)
        arrow = "▲" if close >= open_p else "▼"
        print(f"{date:<10s} {time:<8s} {arrow} {open_p:>8,} {high:>10,} {low:>10,} {close:>10,} {volume:>12,}")
    rest = max(0, len(data) - max_rows)
    if rest:
        print(f"  ... 외 {rest}개 봉")

async def main():
    client = MarketClient(monitor_market_state=False)
    try:
        if not await client.connect():
            return
        today = datetime.now().strftime("%Y%m%d")
        tr = client._repo["t8412"]
        params = tr.build_request({
            "shcode": "005930", "ncnt": 5, "qrycnt": 100,
            "nday": "0", "sdate": "", "stime": "",
            "edate": today, "etime": "",
            "cts_date": "", "cts_time": "", "comp_yn": "N",
        })
        candles = [i async for i in client._api.continuous_query(tr.code, params)]
        print_chart(f"삼성전자 5분봉 ({len(candles)}개)", candles)
    except Exception as e:
        print(f"오류: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
