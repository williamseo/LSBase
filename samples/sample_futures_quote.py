import asyncio
from lsbase import MarketClient

async def main():
    client = MarketClient(monitor_market_state=False)
    try:
        if not await client.connect():
            return
        quote = await client.futures.get_quote("101P3000")
        print(f"=== KOSPI200선물 12월물 ===")
        print(f"종목명: {quote.symbol_name}")
        print(f"현재가: {quote.current_price:,.2f}")
        print(f"전일대비: {quote.change:+,.2f} ({quote.change_rate:+.2f}%)")
        print(f"고가: {quote.high:,.2f} / 저가: {quote.low:,.2f}")
        print(f"거래량: {quote.volume:,}")
    except Exception as e:
        print(f"오류: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
