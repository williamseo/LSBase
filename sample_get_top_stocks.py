# sample_get_top_stocks.py

import asyncio
from lsbase import MarketClient
from lsbase.core.models import MarketCapStock

def print_stock_list(title: str, stocks: list[MarketCapStock]):
    total_stocks = len(stocks)

    print(f"\n{'='*25} {title} (총 {total_stocks}개) {'='*25}")
    print(f"{'순위':>6} | {'종목명':<15} | {'종목코드':<8} | {'현재가 (원)':>12} | {'시가총액 (억 원)':>15}")
    print("-" * 80)

    # 출력할 리스트를 별도로 만들지 않고, 직접 반복문으로 제어합니다.
    stocks_to_print = stocks[:10]
    
    for stock in stocks_to_print:
        price = f"{stock.price:,}"
        market_cap = f"{stock.market_cap_in_b_krw:,}"
        print(f"{stock.rank!s:>6} | {stock.name:<15} | {stock.code:<8} | {price:>12} | {market_cap:>15}")
    
    # 총 개수가 15개를 초과할 경우에만 구분선과 하위 종목을 출력합니다.
    if total_stocks > 15:
        print(f"{'...':>6} | {'...':<15} | {'...':<8} | {'...':>12} | {'...':>15}")
        
        for stock in stocks[-5:]:
            price = f"{stock.price:,}"
            market_cap = f"{stock.market_cap_in_b_krw:,}"
            print(f"{stock.rank!s:>6} | {stock.name:<15} | {stock.code:<8} | {price:>12} | {market_cap:>15}")
              
    print("=" * 80)
async def main():
    client = MarketClient()
    try:
        if not await client.connect():
            return

        stock_market = client.stock

        kospi_top_100 = await stock_market.get_top_market_cap_stocks("KOSPI", limit=100)
        print_stock_list("KOSPI 시가총액 Top 100", kospi_top_100)
        
        kosdaq_top_100 = await stock_market.get_top_market_cap_stocks("KOSDAQ", limit=100)
        print_stock_list("KOSDAQ 시가총액 Top 100", kosdaq_top_100)

    except Exception as e:
        print(f"\n오류가 발생했습니다: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
