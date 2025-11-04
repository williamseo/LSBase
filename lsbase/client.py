# lsbase/client.py
import os
import logging
import asyncio
from datetime import datetime
from . import config
from .openapi_client.OpenApi import OpenApi
from .api_client.ls_api import LSTradingAPI
from .markets.stock import StockMarket
from .logger import setup_logger # 로거 설정 함수 임포트
from .tr_adapter import TrCodeAdapter
from .core.enum import RealtimeType
from .core.models import MarketState, MarketStatus

# 모듈 레벨 로거 설정
logger = logging.getLogger(__name__)

class MarketClient:
    def __init__(self,
                 app_key: str,
                 app_secret: str,
                 account_no: str,
                 account_pw: str,
                 monitor_market_state: bool = True,
                 specs_filepath: str = None):

        setup_logger()

        self.app_key = app_key
        self.app_secret = app_secret

        base_dir = os.path.dirname(os.path.abspath(__file__))
        final_specs_path = specs_filepath or os.path.join(base_dir, 'tools', 'ls_openapi_specs.json')

        self.spec = TrCodeAdapter(specs_filepath=final_specs_path)
        logger.info("TR 명세 어댑터(spec)가 성공적으로 로드되었습니다.")

        self._open_api = OpenApi()
        self._api = LSTradingAPI(self._open_api)
        
        self.stock = StockMarket(
            api=self._api, 
            spec=self.spec, # spec 객체를 전달
            account_no=account_no, 
            account_pw=account_pw
        )

        self._monitor_market_state = monitor_market_state
        self._background_tasks = []
        self._server_time: datetime | None = None
        self.market_states: dict[str, MarketState] = {
            "1": MarketState(market_name="코스피"),
            "2": MarketState(market_name="코스닥"),
            "8": MarketState(market_name="KRX야간파생"),
            "9": MarketState(market_name="미국주식"),
        }

        self._open_api.on_message.connect(self.on_message_received)
        # JIF와 NWS 핸들러를 분리하여 관리
        if self._monitor_market_state:
            self._open_api.on_realtime.connect(self._internal_jif_handler)
        self._open_api.on_realtime.connect(self.on_realtime_data_received)

    async def connect(self) -> bool:
        logger.info("API 서버에 연결을 시도합니다...")
        is_connected = await self._open_api.login(self.app_key, self.app_secret)

        if is_connected:
            logger.info("API 서버 연결 성공.")
        else:
            logger.error(f"API 서버 연결 실패: {self._open_api.last_message}")

        if self._monitor_market_state:
            logger.info("기본 모니터링(장운영정보, 서버시간)을 시작합니다.")
            jif_task = asyncio.create_task(self._subscribe_all_jif())
            time_task = asyncio.create_task(self._periodic_server_time_checker())
            self._background_tasks.extend([jif_task, time_task])
            
        return is_connected

    async def disconnect(self):
        logger.info("백그라운드 작업을 종료하고 API 연결을 종료합니다.")
        
        # 1. 생성된 모든 백그라운드 태스크를 취소합니다.
        for task in self._background_tasks:
            task.cancel()
        
        # 2. 모든 태스크가 완전히 종료될 때까지 기다립니다.
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            
        # 3. 모든 작업이 정리된 후, API 연결을 닫습니다.
        await self._open_api.close()

    def on_message_received(self, sender, msg):
        logger.info(f"[API Message]: {msg}")

    def on_realtime_data_received(self, sender, trcode, key, realtimedata):
        logger.debug(f"[Realtime Data] TR: {trcode}, Key: {key}, Data: {realtimedata}")

    @property
    def server_time(self) -> datetime | None:
        """가장 최근에 동기화된 서버 시간을 반환합니다."""
        return self._server_time

    def get_market_state(self, market_code: str) -> MarketState | None:
        """지정된 시장의 현재 상태를 반환합니다. (market_code: "1", "2", "8", "9" 등)"""
        return self.market_states.get(market_code)

    def is_market_open(self, market_code: str) -> bool:
        """지정된 시장이 현재 정규장 시간인지 확인합니다."""
        state = self.get_market_state(market_code)
        return state.status == MarketStatus.OPEN if state else False

    async def _subscribe_all_jif(self):
        """지원하는 모든 시장의 JIF를 구독합니다."""
        for key in self.market_states.keys():
            await self.stock.subscribe_realtime(key, RealtimeType.MARKET_STATUS)

    async def _periodic_server_time_checker(self):
        """주기적으로 서버 시간을 동기화하는 내부 백그라운드 작업"""
        while True:
            try:
                time_str = await self.stock.get_server_time()
                self._server_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[서버 시간 동기화 오류]: {e}")
            await asyncio.sleep(60) # 1분 간격

    def _internal_jif_handler(self, sender, trcode, key, realtimedata):
        """수신된 JIF 데이터를 해석하여 내부 market_states를 업데이트합니다."""
        if trcode != "JIF":
            return

        state = self.market_states.get(key)
        if not state:
            return

        status_code = realtimedata.get('jstatus')
        new_status = self._convert_jstatus_to_marketstatus(status_code)

        if state.status != new_status:
            logger.info(f"시장 상태 변경: {state.market_name} ({state.status.value} -> {new_status.value})")
            state.status = new_status
            state.last_updated = datetime.now()
            state.raw_jstatus_code = status_code

    def _convert_jstatus_to_marketstatus(self, jstatus: str) -> MarketStatus:
        """JIF 상태 코드를 내부 MarketStatus Enum으로 변환합니다."""
        if jstatus in ("11", "22", "23", "24", "25", "55", "57"):
            return MarketStatus.PRE_MARKET
        if jstatus == "21":
            return MarketStatus.OPEN
        if jstatus in ("31", "56", "58"):
            return MarketStatus.POST_MARKET
        if jstatus == "41":
            return MarketStatus.CLOSED
        if jstatus == "52":
            return MarketStatus.DANILGA
        return MarketStatus.UNKNOWN
