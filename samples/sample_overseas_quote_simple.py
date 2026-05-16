import asyncio
from lsbase import MarketClient

STOCKS = [
    ("TSLA", "82", "테슬라"),
    ("AAPL", "82", "애플"),
    ("NVDA", "82", "엔비디아"),
]

async def main():
    client = MarketClient(monitor_market_state=False)
    try:
        if not await client.connect():
            return
        print(f"=== 해외주식 현재가 ===")
        print(f"  {'종목명':<12s} {'티커':<8s} {'현재가':>12s} {'변동':>10s}")
        print(f"  {'-'*44}")
        for symbol, exchcd, name in STOCKS:
            quote = await client.overseas.get_quote(symbol, exchcd)
            print(f"  {name:<12s} {symbol:<8s} {quote.current_price:>10,.2f}$ {quote.change:>+9.2f}$")
            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"오류: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
