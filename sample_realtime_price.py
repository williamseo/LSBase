# sample_realtime_price.py

import asyncio
import datetime
from lsbase import MarketClient

def on_samsung_price_update(sender, trcode, key, realtimedata):
    """
    실시간 데이터를 수신했을 때 호출되는 핸들러 함수입니다.
    삼성전자(005930)의 주식 체결(S3_) 데이터만 필터링하여 출력합니다.
    """
    # 이 예제에서는 삼성전자(key="005930")의 체결(trcode="S3_") 데이터만 처리합니다.
    if trcode == "S3_" and key == "005930":
        chetime = realtimedata.get('chetime', '')  # 체결시간 (HHMMSS)
        price = int(realtimedata.get('price', 0))    # 현재가
        cvolume = int(realtimedata.get('cvolume', 0))  # 체결량
        
        # 보기 쉽게 시간 형식을 변경합니다. (HHMMSS -> HH:MM:SS)
        formatted_time = f"{chetime[:2]}:{chetime[2:4]}:{chetime[4:]}"
        
        print(f"[실시간 체결] 시간: {formatted_time}, 현재가: {price: ,d} 원, 체결량: {cvolume: ,d} 주")

async def main():
    client = MarketClient(False)
    samsung_symbol = "005930"
    
    try:
        # ----------------- 수정된 부분 -----------------
        # MarketClient의 내부 객체인 _open_api의 on_realtime 이벤트에 핸들러를 연결합니다.
        client._open_api.on_realtime.connect(on_samsung_price_update)
        # -----------------------------------------------
        
        # API 서버에 접속 및 로그인
        if not await client.connect():
            print("서버 연결에 실패했습니다.")
            return

        print(f"\n삼성전자({samsung_symbol}) 실시간 체결가 수신을 시작합니다.")
        print("60초 후 자동으로 종료됩니다. (수동 종료: Ctrl+C)")
        
        # 실시간 데이터 구독 요청 (TR Code: S3_ - 주식 체결)
        is_subscription_successful = await client._open_api.add_realtime("S3_", samsung_symbol)

        if not is_subscription_successful:
            print("실시간 데이터 구독 요청에 실패했습니다.")
            return

        # 60초 동안 실시간 데이터를 수신하며 대기합니다.
        await asyncio.sleep(60)
        
        print("\n60초가 경과하여 실시간 수신을 중단합니다.")

    except (KeyboardInterrupt, asyncio.CancelledError):
        # 사용자가 Ctrl+C를 눌러 종료한 경우
        print("\n프로그램을 종료합니다.")
    except Exception as e:
        print(f"오류가 발생했습니다: {e}")
    finally:
        # ----------------- 수정된 부분 -----------------
        # MarketClient의 내부 객체인 _open_api의 connected 속성을 확인합니다.
        if client._open_api.connected:
        # -----------------------------------------------
            print("실시간 데이터 구독을 해제하고 연결을 종료합니다.")
            await client._open_api.remove_realtime("S3_", samsung_symbol)
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
