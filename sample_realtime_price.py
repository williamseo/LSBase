import asyncio
from lsbase import MarketClient


def on_samsung_price_update(sender, trcode, key, realtimedata):
    if trcode == "S3_" and key == "005930":
        try:
            chetime = realtimedata.get("chetime", "")
            price = realtimedata.get("price", "0")
            cvolume = realtimedata.get("cvolume", "0")

            if chetime and price:
                formatted_time = f"{chetime[:2]}:{chetime[2:4]}:{chetime[4:]}"
                print(f"[실시간 체결] 시간: {formatted_time}, 현재가: {int(price):,d} 원, 체결량: {int(cvolume):,d} 주")

        except (ValueError, TypeError) as e:
            print(f"S3_ 처리 오류: {e}")


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
