# sample_realtime_price.py (v8.0 최종)

import asyncio
from lsbase import MarketClient
from lsbase import generated_models as gen_models
from pydantic import ValidationError

def on_samsung_price_update(sender, trcode, key, realtimedata):
    if trcode == "S3_" and key == "005930":
        try:
            # 이제 S3Response는 realtimedata와 구조가 일치하는 평평한 모델입니다.
            data = gen_models.S3Response.model_validate(realtimedata)
            
            if data.chetime and data.price and data.cvolume:
                chetime = data.chetime
                price = int(data.price)
                cvolume = int(data.cvolume)
                
                formatted_time = f"{chetime[:2]}:{chetime[2:4]}:{chetime[4:]}"
                print(f"[실시간 체결] 시간: {formatted_time}, 현재가: {price: ,d} 원, 체결량: {cvolume: ,d} 주")

        except ValidationError as e:
            print(f"S3_ 데이터 파싱 오류: {e}")
        except (AttributeError, TypeError, ValueError) as e:
            # 'S3Response' 모델 자체가 없는 경우를 대비한 예외 처리
            if 'has no attribute' in str(e):
                 print(f"오류: 'generated_models.py'에 '{e.name}' 모델이 없습니다. 코드 생성기를 다시 실행하세요.")
            else:
                 print(f"S3_ 처리 오류: {e}. realtimedata: {realtimedata}")

# async def main() 부분은 이전과 동일
async def main():
    client = MarketClient(monitor_market_state=False) 
    samsung_symbol = "005930"
    try:
        client._open_api.on_realtime.connect(on_samsung_price_update)
        if not await client.connect():
            print("서버 연결에 실패했습니다.")
            return
        print(f"\n삼성전자({samsung_symbol}) 실시간 체결가 수신을 시작합니다.")
        print("60초 후 자동으로 종료됩니다. (수동 종료: Ctrl+C)")
        is_subscription_successful = await client._open_api.add_realtime("S3_", samsung_symbol)
        if not is_subscription_successful:
            print("실시간 데이터 구독 요청에 실패했습니다.")
            return
        await asyncio.sleep(60)
        print("\n60초가 경과하여 실시간 수신을 중단합니다.")
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n프로그램을 종료합니다.")
    except Exception as e:
        print(f"오류가 발생했습니다: {e}")
    finally:
        if client._open_api and client._open_api.connected:
            print("실시간 데이터 구독을 해제하고 연결을 종료합니다.")
            await client._open_api.remove_realtime("S3_", samsung_symbol)
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
