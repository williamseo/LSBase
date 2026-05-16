# sample_get_price.py

import asyncio
from lsbase import MarketClient

async def main():
    client = MarketClient(monitor_market_state=False)
    try:
        if not await client.connect():
            return

        stock_market = client.stock
        samsung_symbol = "005930"
        print(f"\n'{samsung_symbol}'의 현재가 조회를 요청합니다...")
        
        quote = await stock_market.get_quote(samsung_symbol)
        
        print("\n--- 조회 결과 ---")
        print(f"종목명: {quote.symbol_name}")
        print(f"현재가: {quote.current_price:,.0f} 원")
        print(f"거래량: {quote.volume:,} 주")
        print("-----------------")

    except Exception as e:
        print(f"오류가 발생했습니다: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
