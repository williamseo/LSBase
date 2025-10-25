import asyncio
from lsbase import MarketClient

async def main():
    """
    LSBase 프레임워크를 사용하여 삼성전자 현재가를 조회하는 샘플 프로그램
    """
    client = MarketClient()
    
    try:
        # .env 파일의 정보로 API 서버에 연결
        if not await client.connect():
            return

        # 국내 주식 시장 객체에 접근
        stock_market = client.stock
        
        # 삼성전자(005930)의 현재가 조회
        samsung_symbol = "005930"
        print(f"\n'{samsung_symbol}'의 현재가 조회를 요청합니다...")
        
        quote = await stock_market.get_quote(samsung_symbol)
        
        print("\n--- 조회 결과 ---")
        print(f"종목명: {quote['symbol_name']}")
        print(f"현재가: {quote['current_price']:,} 원")
        print(f"거래량: {quote['volume']:,} 주")
        print("-----------------")

    except Exception as e:
        print(f"오류가 발생했습니다: {e}")
    finally:
        # 프로그램 종료 전 항상 연결을 안전하게 종료
        await client.disconnect()


if __name__ == "__main__":
    # 비동기 함수 실행
    asyncio.run(main())
