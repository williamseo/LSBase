# integrated_monitor.py
# 이 스크립트는 LS Securities API를 사용하여 세 가지 TR 코드(t0167, JIF, NWS)의 기능을 통합합니다.
# - t0167: 서버 시간 조회 (기준 시간 설정 및 로그 타임스탬프용)
# - JIF: 실시간 시장 운영 정보 (시스템 동작 모드 제어, 오류 방지)
# - NWS: 실시간 뉴스 헤드라인 (리스크 관리, 변동성 경고, 이벤트 감지)
#
# 통합 로직:
# 1. 서버 시간을 주기적으로 조회하여 시스템의 시간 기준을 유지.
# 2. 시장 상태(JIF)를 실시간으로 모니터링하여 시스템 동작(예: 트레이딩 시작/정지)을 제어.
# 3. 뉴스 헤드라인(NWS)을 실시간으로 수신하여 키워드 기반 경고(예: '변동성', '리스크')를 트리거.
# 4. 모든 데이터를 로그에 타임스탬프로 기록하고, 이벤트 발생 시 알림(콘솔 출력).

import asyncio
import logging
import time
from datetime import datetime
from lsbase import MarketClient  # 제공된 MarketClient import (문서 기반)

# 로거 설정 (문서의 setup_logger 사용 가능, 여기서는 간단히 재구현)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IntegratedMonitor:
    def __init__(self, client: MarketClient):
        self.client = client
        self.server_time_offset = 0  # 서버 시간과 로컬 시간 차이 (초 단위)
        self.market_status = "UNKNOWN"  # 시장 상태 (OPEN, CLOSED 등)
        self.news_keywords = ['변동성', '리스크', '경고', '충격', '하락']  # 감지할 뉴스 키워드

        # 실시간 핸들러 연결
        self.client._open_api.on_realtime.connect(self._handle_realtime_data)
        self.client._open_api.on_message.connect(self._handle_api_message)

    async def _query_server_time(self) -> str:
        """t0167 TR을 사용하여 서버 시간 조회."""
        tr_code = "t0167"
        params = {}  # t0167은 빈 파라미터로 동작 (문서 확인)
        try:
            response = await self.client._api.query(tr_code, params)
            server_time = response.body.get("t0167OutBlock", {}).get("dt", "Unknown")
            logger.info(f"서버 시간 조회: {server_time}")
            
            # 시간 오프셋 계산 (로컬 시간과 비교)
            local_time = datetime.now().strftime("%Y%m%d%H%M%S")
            self.server_time_offset = (datetime.strptime(server_time, "%Y%m%d%H%M%S") - 
                                       datetime.strptime(local_time, "%Y%m%d%H%M%S")).total_seconds()
            return server_time
        except Exception as e:
            logger.error(f"t0167 조회 실패: {e}")
            return "Unknown"

    async def subscribe_market_status(self) -> bool:
        """JIF 실시간 구독 (시장 운영 정보)."""
        return await self.client._open_api.add_realtime("JIF", "")  # 키는 빈 문자열 (전체 시장)

    async def subscribe_news(self) -> bool:
        """NWS 실시간 구독 (뉴스 헤드라인)."""
        return await self.client._open_api.add_realtime("NWS", "")  # 키는 빈 문자열 (모든 뉴스)

    async def unsubscribe_all(self):
        """모든 실시간 구독 해제."""
        await self.client._open_api.remove_realtime("JIF", "")
        await self.client._open_api.remove_realtime("NWS", "")

    def _handle_realtime_data(self, sender, trcode: str, key: str, realtimedata: dict):
        """실시간 데이터 핸들러 (JIF와 NWS 처리)."""
        current_time = self._get_adjusted_time()  # 서버 시간 기준 타임스탬프
        
        if trcode == "JIF":
            # 시장 상태 업데이트 (예: 시장 개장/폐장 정보)
            status = realtimedata.get('market_status', 'UNKNOWN')  # 가정: 실제 키는 문서 확인 필요
            if status != self.market_status:
                self.market_status = status
                logger.info(f"{current_time} - 시장 상태 변경: {status}")
                if status == "CLOSED":
                    logger.warning(f"{current_time} - 시장 폐장: 트레이딩 중지 권고")

        elif trcode == "NWS":
            # 뉴스 헤드라인 처리
            headline = realtimedata.get('headline', '')  # 가정: 실제 키는 문서 확인 필요
            logger.info(f"{current_time} - 뉴스 수신: {headline}")
            # 키워드 기반 이벤트 감지
            for keyword in self.news_keywords:
                if keyword in headline:
                    logger.warning(f"{current_time} - 변동성 경고: '{keyword}' 키워드 감지 ({headline})")
                    # 추가 로직: 이메일 알림이나 트레이딩 정지 등

    def _handle_api_message(self, sender, msg: str):
        """API 메시지 핸들러 (오류나 일반 메시지 로그)."""
        current_time = self._get_adjusted_time()
        logger.info(f"{current_time} - API 메시지: {msg}")

    def _get_adjusted_time(self) -> str:
        """서버 시간 오프셋을 적용한 현재 시간 반환."""
        local_now = datetime.now()
        adjusted = local_now + datetime.timedelta(seconds=self.server_time_offset)
        return adjusted.strftime("%Y-%m-%d %H:%M:%S")

    async def run_monitor(self, duration: int = 300):
        """통합 모니터링 실행 (duration 초 동안)."""
        await self._query_server_time()  # 초기 서버 시간 조회
        
        if not await self.subscribe_market_status():
            logger.error("JIF 구독 실패")
            return
        if not await self.subscribe_news():
            logger.error("NWS 구독 실패")
            return
        
        logger.info("통합 모니터링 시작 (t0167 시간 기준, JIF 시장 상태, NWS 뉴스 감지)")
        try:
            await asyncio.sleep(duration)  # 모니터링 기간
        except asyncio.CancelledError:
            pass
        finally:
            await self.unsubscribe_all()
            logger.info("통합 모니터링 종료")

async def main():
    client = MarketClient()
    try:
        if not await client.connect():
            logger.error("API 연결 실패")
            return

        monitor = IntegratedMonitor(client)
        await monitor.run_monitor(duration=60)  # 60초 테스트 실행 (실제로는 더 길게)

    except Exception as e:
        logger.error(f"오류 발생: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
