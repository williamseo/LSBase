# lsbase/client.py
import logging
from . import config
from .openapi_client.OpenApi import OpenApi
from .api_client.ls_api import LSTradingAPI
from .markets.stock import StockMarket
from .logger import setup_logger # 로거 설정 함수 임포트

# 모듈 레벨 로거 설정
logger = logging.getLogger(__name__)

class MarketClient:
    def __init__(self):
        # 최상위 로거 설정 (최초 한 번만 실행됨)
        setup_logger()

        self._open_api = OpenApi()
        self._api = LSTradingAPI(self._open_api)
        
        # Market 클래스에도 로거를 주입해줄 수 있음
        self.stock = StockMarket(
            api=self._api, 
            account_no=config.ACCOUNT_NO, 
            account_pw=config.ACCOUNT_PASSWORD
        )

        self._open_api.on_message.connect(self.on_message_received)
        self._open_api.on_realtime.connect(self.on_realtime_data_received)

    async def connect(self) -> bool:
        logger.info("API 서버에 연결을 시도합니다...")
        is_connected = await self._open_api.login(config.APP_KEY, config.APP_SECRET)
        if is_connected:
            logger.info("API 서버 연결 성공.")
        else:
            logger.error(f"API 서버 연결 실패: {self._open_api.last_message}")
        return is_connected

    async def disconnect(self):
        logger.info("API 연결을 종료합니다.")
        await self._open_api.close()
    
    def on_message_received(self, sender, msg):
        logger.info(f"[API Message]: {msg}")

    def on_realtime_data_received(self, sender, trcode, key, realtimedata):
        logger.debug(f"[Realtime Data] TR: {trcode}, Key: {key}, Data: {realtimedata}")
