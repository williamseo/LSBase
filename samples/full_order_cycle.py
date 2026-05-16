import asyncio
from lsbase import MarketClient
from lsbase.core.enum import OrderSide, OrderType

def on_realtime_order_status(sender, trcode, key, realtimedata):
    tr_status_map = {
        "SC0": "주문접수",
        "SC1": "주문체결",
        "SC2": "주문정정",
        "SC3": "주문취소",
        "SC4": "주문거부",
    }
    status = tr_status_map.get(trcode, trcode)
    order_no = realtimedata.get('ordno', 'N/A')
    stock_code = realtimedata.get('shtnIsuno') or realtimedata.get('shtcode', 'N/A')
    account_no = realtimedata.get('accno', key)
    exec_qty = realtimedata.get('execqty', 0)
    exec_price = realtimedata.get('execprc', 0)
    
    print("\n======================================")
    print(f"📢 [실시간 주문 상태 수신]")
    print(f"   - 상태: {status} ({trcode})")
    print(f"   - 주문번호: {order_no}")
    print(f"   - 종목코드: {stock_code}")
    if trcode == 'SC1':
        print(f"   - 체결수량: {int(exec_qty):,} 주")
        print(f"   - 체결가격: {float(exec_price):,.0f} 원")
    print(f"   - (계좌번호: {account_no})")
    print("======================================")

async def main():
    client = MarketClient(monitor_market_state=False)
    # SC2(주문정정) 추가
    realtime_tr_codes = ["SC0", "SC1", "SC2", "SC3", "SC4"]
    account_no = None
    original_order_no = None

    try:
        client._open_api.on_realtime.connect(on_realtime_order_status)
        
        if not await client.connect():
            print("오류: API 서버 연결에 실패했습니다.")
            return

        account_no = client.stock.account_no
        print(f"\n실시간 주문 상태 수신을 시작합니다. (계좌: {account_no})")
        for tr_code in realtime_tr_codes:
            await client._open_api.add_realtime(tr_code, account_no)
        
        # --- 시나리오 시작 ---
        stock_symbol = "005930"
        order_quantity = 1
        
        # 1. 200,000원에 지정가 매수 주문 (체결되지 않을 높은 가격)
        print("\n\n--- [1/4] 200,000원에 지정가 매수 주문 요청 ---")
        response = await client.stock.place_order(
            symbol=stock_symbol, quantity=order_quantity, price=90000,
            side=OrderSide.BUY, order_type=OrderType.LIMIT
        )
        if not response.is_success:
            print(f"❌ 초기 주문 실패: {response.message}")
            return
        original_order_no = response.order_id
        print(f"✅ 초기 주문 요청 성공! (주문번호: {original_order_no})")
        await asyncio.sleep(3)

        # 2. 주문을 92000원으로 정정
        print(f"\n\n--- [2/4] 주문번호 {original_order_no}을 92000원으로 정정 요청 ---")
        response = await client.stock.modify_order(
            org_order_no=original_order_no, symbol=stock_symbol,
            quantity=order_quantity, price=92000
        )
        if not response.is_success:
            print(f"❌ 주문 정정 실패: {response.message}")
            return
        # 정정/취소 시 주문번호가 새로 발급될 수 있으므로 업데이트
        original_order_no = response.order_id
        print(f"✅ 주문 정정 요청 성공! (새 주문번호: {original_order_no})")
        await asyncio.sleep(3)

        # 3. 주문 취소
        print(f"\n\n--- [3/4] 주문번호 {original_order_no} 취소 요청 ---")
        response = await client.stock.cancel_order(
            org_order_no=original_order_no, symbol=stock_symbol,
            quantity=order_quantity
        )
        if not response.is_success:
            print(f"❌ 주문 취소 실패: {response.message}")
            return
        print(f"✅ 주문 취소 요청 성공!")
        await asyncio.sleep(5)
        
        # 4. 시장가 매수 주문 (즉시 체결 유도)
        print("\n\n--- [4/4] 시장가 매수 주문 요청 ---")
        response = await client.stock.place_order(
            symbol=stock_symbol, quantity=order_quantity, price=0,
            side=OrderSide.BUY, order_type=OrderType.MARKET
        )
        if not response.is_success:
            print(f"❌ 시장가 주문 실패: {response.message}")
            return
        print(f"✅ 시장가 주문 요청 성공! (주문번호: {response.order_id})")
        print("\n모든 시나리오 완료. 10초 후 종료됩니다.")
        await asyncio.sleep(10)

    except Exception as e:
        print(f"\n스크립트 실행 중 오류가 발생했습니다: {e}")
    finally:
        if client and client._open_api and client._open_api.connected and account_no:
            print("\n실시간 구독을 해제하고 연결을 종료합니다.")
            for tr_code in realtime_tr_codes:
                await client._open_api.remove_realtime(tr_code, account_no)
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
