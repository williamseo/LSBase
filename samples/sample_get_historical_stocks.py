# sample_get_historical_data.py

import asyncio
from lsbase import MarketClient
from lsbase.core.models import HistoricalPrice # 새로 추가될 모델
from datetime import datetime

def print_historical_data(title: str, prices: list[HistoricalPrice]):
    """주어진 기간별 시세 데이터를 보기 좋은 표 형태로 출력합니다."""
    total_prices = len(prices)
    if not prices:
        print(f"\n{'='*25} {title} (총 0개) {'='*25}")
        print("조회된 데이터가 없습니다.")
        print("=" * 80)
        return

    print(f"\n{'='*30} {title} (총 {total_prices}개) {'='*30}")
    print(f"{'날짜':<12} | {'시가':>10} | {'고가':>10} | {'저가':>10} | {'종가':>10} | {'등락율 (%)':>12} | {'거래량':>15}")
    print("-" * 100)

    # 출력할 데이터 개수 제어 (최대 15개)
    prices_to_print = prices[:15]
    
    for price in prices_to_print:
        open_p = f"{price.open:,}"
        high_p = f"{price.high:,}"
        low_p = f"{price.low:,}"
        close_p = f"{price.close:,}"
        volume_p = f"{price.volume:,}"
        diff_p = f"{price.change_rate:.2f}"
        
        print(f"{price.date:<12} | {open_p:>10} | {high_p:>10} | {low_p:>10} | {close_p:>10} | {diff_p:>12} | {volume_p:>15}")
    
    if total_prices > 15:
        print(f"{'...':<12} | {'...':>10} | {'...':>10} | {'...':>10} | {'...':>10} | {'...':>12} | {'...':>15}")
        
    print("=" * 100)

async def main():
    # MarketClient의 monitor_market_state를 False로 설정하여 불필요한 실시간 구독 방지
    client = MarketClient(monitor_market_state=False) 
    try:
        if not await client.connect():
            print("API 서버 연결에 실패했습니다.")
            return

        stock_market = client.stock

        # --- 삼성전자 일별 시세 조회 (최근 100일) ---
        # start_date를 지정하지 않으면 API가 가능한 최신 데이터부터 조회합니다.
        samsung_daily = await stock_market.get_historical_data("005930", period="day", count=100)
        print_historical_data("삼성전자 일별 시세 (최근 100일)", samsung_daily)

        await asyncio.sleep(1)

        # --- SK하이닉스 주별 시세 조회 (2024년 1월 1일부터) ---
        skhynix_weekly = await stock_market.get_historical_data("000660", period="week", start_date="20240101", count=50)
        print_historical_data("SK하이닉스 주별 시세 (2024-01-01~)", skhynix_weekly)

        await asyncio.sleep(1)
        
        # --- 유효하지 않은 종목코드 테스트 ---
        invalid_stock = await stock_market.get_historical_data("000100", period="day", count=10)
        print_historical_data("유효하지 않은 종목", invalid_stock)


    except Exception as e:
        print(f"\n오류가 발생했습니다: {e}")
    finally:
        # 클라이언트 연결 종료
        await client.disconnect()

if __name__ == "__main__":
    # Windows에서 asyncio 실행 시 필요한 이벤트 루프 정책 설정
    if asyncio.get_event_loop().is_running():
         asyncio.create_task(main())
    else:
         asyncio.run(main())
