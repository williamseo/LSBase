import asyncio
from lsbase import MarketClient
from lsbase.core.enum import OrderSide, OrderType

async def main():
    # 모의투자 계좌 정보가 .env 파일에 설정되어 있어야 합니다.
    client = MarketClient(monitor_market_state=False)
    try:
        if not await client.connect():
            return

        stock_market = client.stock
        
        # 모의 투자 환경에서 삼성전자 1주를 현재가보다 훨씬 낮은 가격에
        # 지정가 매수 주문을 넣어 체결되지 않도록 테스트합니다.
        symbol = "005930"
        quantity = 1
        price = 100000  # 체결되지 않을 만한 낮은 가격
        
        print(f"\n[{symbol}] {quantity}주, {price}원 지정가 매수 주문 테스트...")
        
        order_response = await stock_market.place_order(
            symbol=symbol,
            quantity=quantity,
            price=price,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT
        )
        
        print("\n--- 주문 결과 ---")
        if order_response.is_success:
            print(f"✅ 주문 접수 성공!")
            print(f"   - 주문번호: {order_response.order_id}")
        else:
            print(f"❌ 주문 접수 실패")
            print(f"   - 메시지: {order_response.message}")
        print("-----------------")

    except Exception as e:
        print(f"오류가 발생했습니다: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
