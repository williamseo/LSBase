import asyncio
from lsbase import MarketClient
from lsbase.generated_models import T8436InBlock, T8436Request

async def main():
    """
    t8436 TR을 사용하여 코스피와 코스닥의 총 종목 수를 확인하는 샘플 프로그램입니다.
    (.env 파일에서 API 키를 자동으로 로드합니다.)
    """
    client = MarketClient(monitor_market_state=False)
    
    try:
        if not await client.connect():
            print("오류: API 서버 연결에 실패했습니다.")
            return

        # 코스피 조회 (gubun=1)
        print("\n--- 코스피 종목 수 조회 시작 ---")
        params = T8436Request(t8436InBlock=T8436InBlock(gubun="1")).model_dump()
        response = await client._api.query("t8436", params)
        
        if response and response.body:
            kospi_stocks = response.body.get("t8436OutBlock", [])
            kospi_count = len(kospi_stocks)
            print(f"✅ 코스피 총 종목 수: {kospi_count:,}개")
        else:
            print("❌ 코스피 조회 실패: 응답 데이터가 없습니다.")

        # 코스닥 조회 (gubun=2)
        print("\n--- 코스닥 종목 수 조회 시작 ---")
        params = T8436Request(t8436InBlock=T8436InBlock(gubun="2")).model_dump()
        response = await client._api.query("t8436", params)
        
        if response and response.body:
            kosdaq_stocks = response.body.get("t8436OutBlock", [])
            kosdaq_count = len(kosdaq_stocks)
            print(f"✅ 코스닥 총 종목 수: {kosdaq_count:,}개")
        else:
            print("❌ 코스닥 조회 실패: 응답 데이터가 없습니다.")

        # (선택) 전체 조회 (gubun=0)로 검증
        print("\n--- 전체 (코스피 + 코스닥) 종목 수 조회 ---")
        params = T8436Request(t8436InBlock=T8436InBlock(gubun="0")).model_dump()
        response = await client._api.query("t8436", params)
        
        if response and response.body:
            all_stocks = response.body.get("t8436OutBlock", [])
            total_count = len(all_stocks)
            print(f"✅ 전체 총 종목 수: {total_count:,}개 (코스피 + 코스닥 = {kospi_count + kosdaq_count:,}개)")
        else:
            print("❌ 전체 조회 실패: 응답 데이터가 없습니다.")

    except Exception as e:
        print(f"❌ 오류가 발생했습니다: {e}")
    finally:
        if client and client._open_api and client._open_api.connected:
            print("\n--- API 연결 종료 ---")
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
