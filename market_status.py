# sample_realtime_market_status.py (개선된 버전)

import asyncio
import datetime
from datetime import datetime
from lsbase import MarketClient
from lsbase.core.enum import RealtimeType # RealtimeType 임포트

# JIF TR의 jangubun, jstatus 코드를 사람이 읽기 쉬운 텍스트로 변환하기 위한 딕셔너리
MARKET_CODE_MAP = {
    "1": "코스피",
    "2": "코스닥",
    "5": "선물/옵션",
    "9": "미국주식",
}

MARKET_STATUS_MAP = {
    "11": "장전 동시호가 개시",
    "21": "정규장 시작",
    "22": "장 개시 10초 전",
    "23": "장 개시 1분 전",
    "24": "장 개시 5분 전",
    "25": "장 개시 10분 전",
    "31": "장후 동시호가 개시",
    "41": "정규장 마감",
    "42": "장 마감 10초 전",
    "43": "장 마감 1분 전",
    "44": "장 마감 5분 전",
    "51": "시간외 종가매매 개시",
    "52": "시간외 단일가매매 개시",
    "54": "시간외 단일가매매 종료",
    "61": "서킷브레이커(CB) 1단계 발동",
    "64": "사이드카 매도 발동",
    "65": "사이드카 매도 해제",
}

def on_realtime_data_received(sender, trcode, key, realtimedata):
    """
    모든 실시간 데이터를 수신하여 TR 코드에 따라 분기 처리하는 핸들러입니다.
    """
    # 1. JIF (장운영정보) 데이터 처리
    if trcode == "JIF":
        now = datetime.datetime.now().strftime('%H:%M:%S')
        market_code = realtimedata.get('jangubun')
        status_code = realtimedata.get('jstatus')
        market_name = MARKET_CODE_MAP.get(market_code, f"시장({market_code})")
        status_desc = MARKET_STATUS_MAP.get(status_code, f"상태({status_code})")
        print(f"📊 [{now}] {market_name} 상태 변경: {status_desc}")

    # 2. NWS (실시간 뉴스 헤드라인) 데이터 처리
    elif trcode == "NWS":
        news_time_str = realtimedata.get('time', '------')
        title = realtimedata.get('title', '제목 없음').strip()
        
        # 보기 좋게 시간 포맷팅
        formatted_time = f"{news_time_str[:2]}:{news_time_str[2:4]}:{news_time_str[4:6]}"
        print(f"📰 [{formatted_time}] {title}")


# --- 1분마다 서버 시간을 조회하는 백그라운드 작업 함수 (새로 추가) ---
async def periodic_server_time_checker(stock_market: "StockMarket"):
    """1분(60초)마다 서버 시간을 조회하고 출력하는 백그라운드 작업"""
    print("🕒 서버 시간 주기적 조회 작업을 시작합니다 (1분 간격).")
    while True:
        try:
            # 1. StockMarket에 추가한 고수준 메서드를 호출합니다.
            server_time = await stock_market.get_server_time()
            print(f"🕒 [서버 시간]: {server_time}")
            
            # 2. 다음 조회를 위해 60초 대기합니다.
            await asyncio.sleep(60)
            
        except asyncio.CancelledError:
            # 작업이 취소되면 루프를 종료합니다.
            print("🕒 서버 시간 조회 작업이 중단되었습니다.")
            break
        except Exception as e:
            print(f"🕒 [서버 시간 조회 오류]: {e}")
            # 오류 발생 시에도 5초 후 재시도합니다.
            await asyncio.sleep(5)


async def main():
    client = MarketClient()
    stock_market = client.stock
    market_keys = ["1", "2"]
    news_tr_key = "NWS001"
    
    # 백그라운드 작업을 관리하기 위한 변수
    time_checker_task = None
    
    try:
        client._open_api.on_realtime.connect(on_realtime_data_received)

        
        if not await client.connect():
            return

        # 1. 오늘 날짜의 장 마감 시간을 설정합니다 (오후 4시).
        now = datetime.now()
        market_close_time = now.replace(hour=16, minute=0, second=0, microsecond=0)

        # 2. 만약 현재 시간이 이미 장 마감 시간을 지났다면, 프로그램을 바로 종료합니다.
        if now >= market_close_time:
            print(f"이미 장 마감 시간({market_close_time.strftime('%H:%M:%S')})이 지났으므로 프로그램을 종료합니다.")
            return

        print("\n'JIF' (장운영정보) 실시간 수신을 시작합니다.")
        print(f"장 마감 시간({market_close_time.strftime('%H:%M:%S')})까지 자동으로 실행됩니다.")
        
        for key in market_keys:
            await stock_market.subscribe_realtime(key, RealtimeType.MARKET_STATUS)

        await stock_market.subscribe_realtime(news_tr_key, RealtimeType.NEWS_HEADLINE)

        # --- 서버 시간 조회 백그라운드 작업을 시작합니다 ---
        time_checker_task = asyncio.create_task(
            periodic_server_time_checker(stock_market)
        )

        while datetime.now() < market_close_time:
            await asyncio.sleep(1)
        
        print(f"\n장 마감 시간({market_close_time.strftime('%H:%M:%S')})이 되어 프로그램을 종료합니다.")

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n프로그램을 종료합니다.")
    except Exception as e:
        print(f"오류가 발생했습니다: {e}")
    finally:
        # --- 프로그램 종료 시 모든 작업을 정리합니다 ---
        if time_checker_task:
            # 실행 중인 백그라운드 작업을 안전하게 취소합니다.
            time_checker_task.cancel()

        if client._open_api.connected:
            print("실시간 데이터 구독을 모두 해제하고 연결을 종료합니다.")
            # 구독 해제 작업들을 병렬로 실행하여 빠르게 처리합니다.
            unsubscribe_tasks = [
                stock_market.unsubscribe_realtime(key, RealtimeType.MARKET_STATUS)
                for key in market_keys
            ]
            await asyncio.gather(*unsubscribe_tasks)
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
