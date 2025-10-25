# sample_get_top_stocks.py

import asyncio
from lsbase import MarketClient

def print_stock_list(title: str, stocks: list[dict]):
    """조회된 종목 리스트를 보기 좋게 출력하는 함수"""
    
    total_stocks = len(stocks)
    # 상위 10개와 하위 5개만 출력 (전체는 너무 많으므로)
    stocks_to_print = stocks[:10]
    if total_stocks > 15:
        stocks_to_print.append({"rank": "...", "name": "...", "code": "...", "price": "...", "market_cap_in_b_krw": "..."})
        stocks_to_print.extend(stocks[-5:])

    print(f"\n{'='*25} {title} (총 {total_stocks}개) {'='*25}")
    print(f"{'순위':>6} | {'종목명':<15} | {'종목코드':<8} | {'현재가 (원)':>12} | {'시가총액 (억 원)':>15}")
    print("-" * 80)
    
    for stock in stocks_to_print:
        rank = stock['rank']
        price = f"{stock['price']:,}" if isinstance(stock['price'], int) else "..."
        market_cap = f"{stock['market_cap_in_b_krw']:,}" if isinstance(stock['market_cap_in_b_krw'], int) else "..."
        
        print(f"{rank!s:>6} | {stock['name']:<15} | {stock['code']:<8} | {price:>12} | {market_cap:>15}")
              
    print("=" * 80)


async def main():
    """
    [수정] KOSPI와 KOSDAQ 각각 시가총액 상위 100개 종목을 조회합니다.
    """
    client = MarketClient()
    
    try:
        if not await client.connect():
            return

        stock_market = client.stock

        # [수정] KOSPI 시가총액 상위 100개 종목을 조회합니다.
        kospi_top_100 = await stock_market.get_top_market_cap_stocks("KOSPI", limit=100)
        print_stock_list("KOSPI 시가총액 Top 100", kospi_top_100)
        
        # [추가] KOSDAQ 시가총액 상위 100개 종목을 조회합니다.
        kosdaq_top_100 = await stock_market.get_top_market_cap_stocks("KOSDAQ", limit=100)
        print_stock_list("KOSDAQ 시가총액 Top 100", kosdaq_top_100)

    except Exception as e:
        print(f"\n오류가 발생했습니다: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
