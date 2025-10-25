from . import config
from .openapi_client.OpenApi import OpenApi
from .api_client.ls_api import LSTradingAPI
from .markets.stock import StockMarket

class MarketClient:
    def __init__(self):
        self._open_api = OpenApi()
        self._api = LSTradingAPI(self._open_api)

        self.stock = StockMarket(
            api=self._api, 
            account_no=config.ACCOUNT_NO, 
            account_pw=config.ACCOUNT_PASSWORD
        )
        # self.futures = FuturesMarket(...) # 향후 확장

        self._open_api.on_message.connect(self.on_message_received)
        self._open_api.on_realtime.connect(self.on_realtime_data_received)

    async def connect(self) -> bool:
        print("API 서버에 연결을 시도합니다...")
        is_connected = await self._open_api.login(config.APP_KEY, config.APP_SECRET)
        if is_connected:
            print("연결 성공.")
        else:
            print(f"연결 실패: {self._open_api.last_message}")
        return is_connected

    async def disconnect(self):
        print("API 연결을 종료합니다.")
        await self._open_api.close()
    
    def on_message_received(self, sender, msg):
        print(f"[API Message]: {msg}")

    def on_realtime_data_received(self, sender, trcode, key, realtimedata):
        print(f"[Realtime Data] TR: {trcode}, Key: {key}, Data: {realtimedata}")
