import asyncio
from lsbase import MarketClient

OVERSEAS_STOCKS = [
    ("82TSLA", "82", "TSLA", "테슬라"),
    ("82AAPL", "82", "AAPL", "애플"),
    ("82NVDA", "82", "NVDA", "엔비디아"),
    ("82MSFT", "82", "MSFT", "마이크로소프트"),
    ("82AMZN", "82", "AMZN", "아마존"),
    ("81SPY",  "81", "SPY",  "SPY S&P500 ETF"),
    ("81QQQ",  "81", "QQQ",  "QQQ 나스닥 ETF"),
]

async def main():
    client = MarketClient(monitor_market_state=False)
    try:
        if not await client.connect():
            return
        tr = client._repo["g3101"]
        print(f"=== 해외주식 현재가 ===\n")
        print(f"  {'종목명':<20s} {'티커':<8s} {'거래소':<6s} {'현재가':>12s} {'전일비':>10s} {'등락율':>8s}")
        print(f"  {'-'*66}")
        for keysymbol, exchcd, symbol, name in OVERSEAS_STOCKS:
            params = tr.build_request({
                "delaygb": "R",
                "keysymbol": keysymbol,
                "exchcd": exchcd,
                "symbol": symbol,
            })
            response = await client._api.query(tr.code, params)
            parsed = tr.parse_response(response.body)
            data = parsed.get("g3101OutBlock", {})
            price = data.get("price", "-")
            change = data.get("change", "-")
            diff = data.get("diff", "-")
            arrow = "▲" if str(diff).lstrip("-").replace(".","").isdigit() and float(diff or 0) >= 0 else "▼"
            print(f"  {name:<20s} {symbol:<8s} NYSE:{exchcd:<2s} {str(price):>>10s} {arrow} {str(change):>8s} {str(diff):>7s}%")
            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"오류: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
