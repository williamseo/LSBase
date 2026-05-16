import asyncio
from lsbase import MarketClient

async def main():
    client = MarketClient(monitor_market_state=False)
    try:
        if not await client.connect():
            return

        print("\n계좌 잔고 조회를 요청합니다...")
        balance = await client.stock.get_account_balance()
        
        print("\n--- 계좌 잔고 정보 ---")
        print(f"예수금: {balance.cash:,} 원")
        print(f"총 매입금액: {balance.total_purchase_amount:,} 원")
        print(f"총 평가금액: {balance.total_evaluation_amount:,} 원")
        print(f"예탁자산총액: {balance.total_assets:,} 원")
        print(f"손익율: {balance.profit_loss_rate:.2f} %")
        print("----------------------")

    except Exception as e:
        print(f"\n오류가 발생했습니다: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
