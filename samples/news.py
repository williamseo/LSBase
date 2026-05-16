# new_sample.py (리팩토링된 lsbase를 사용하는 예시)

import asyncio
from datetime import datetime
from lsbase import MarketClient
from lsbase.core.enum import RealtimeType

def news_handler(sender, trcode, key, realtimedata):
    """사용자가 직접 정의하는 뉴스 수신 핸들러"""
    if trcode == "NWS":
        news_time_str = realtimedata.get('time', '------')
        title = realtimedata.get('title', '제목 없음').strip()
        formatted_time = f"{news_time_str[:2]}:{news_time_str[2:4]}:{news_time_str[4:6]}"
        print(f"📰 [뉴스 수신] {formatted_time} - {title}")

async def main():
    # MarketClient 생성 시, JIF와 서버 시간 모니터링이 자동으로 활성화됩니다.
    client = MarketClient()
    
    # 사용자는 뉴스 수신과 같은 추가적인 실시간 데이터만 직접 핸들링합니다.
    client._open_api.on_realtime.connect(news_handler)
    
    try:
        if not await client.connect():
            return
        
        # 뉴스 실시간 구독 요청
        await client.stock.subscribe_realtime("NWS001", RealtimeType.NEWS_HEADLINE)

        print("모니터링 시작. Ctrl+C로 종료하세요.")
        
        # 10초마다 상태를 체크하며 무한 대기
        while True:
            # 내장된 기능을 통해 현재 상태를 매우 쉽게 조회할 수 있습니다.
            server_time_str = client.server_time.strftime('%H:%M:%S') if client.server_time else "동기화 중..."
            kospi_state = client.get_market_state("1")
            
            print(f"--- [상태 체크: {server_time_str}] ---")
            print(f"코스피 시장 상태: {kospi_state.status.value if kospi_state else 'N/A'}")
            print(f"코스피 정규장 열림? {'Yes' if client.is_market_open('1') else 'No'}")
            print("-" * 30)
            
            await asyncio.sleep(10)

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n프로그램 종료 중...")
    finally:
        if client._open_api and client._open_api.connected:
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
