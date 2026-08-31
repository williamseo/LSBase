import aiohttp, asyncio, json, time, logging
from .tr_code_to_path import tr_code_to_path

logger = logging.getLogger(__name__)
from .code_realtime_account import code_realtime_account
from ..core.resilience import (
    ConnectionManager, ConnectionState, ExponentialBackoff, ReconnectionWorker,
)

BASE_URL = "https://openapi.ls-sec.co.kr:8080"
WSS_URL_REAL = "wss://openapi.ls-sec.co.kr:9443/websocket"
WSS_URL_SIMULATION = "wss://openapi.ls-sec.co.kr:29443/websocket"

import warnings


class ResponseValue:
    def __init__(self, path, tr_cd, tr_cont, tr_cont_key, response_text):
        self.path = path
        self.tr_cd = tr_cd
        self.tr_cont = tr_cont
        self.tr_cont_key = tr_cont_key
        self.body = json.loads(response_text)
        self.response_text = response_text
        self.in_tr_cont = str()
        self.in_tr_cont_key = str()
        self.request_text = str()
        self.request_time = 0.0
        self.elapsed_ms = 0.0


class OpenApi:
    class _event_signal:
        class _slot:
            def __init__(self, func):
                self.func = func
                self.is_coroutine = asyncio.iscoroutinefunction(func)
            def __eq__(self, other):
                return self.func == other
        def __init__(self):
            self.__slots = []
        def connect(self, func):
            if not hasattr(func, "__call__"):
                raise ValueError("slot must be callable")
            if not any(s.func == func for s in self.__slots):
                self.__slots.append(self._slot(func))
        def disconnect(self, func):
            self.__slots = [s for s in self.__slots if s.func != func]
        def disconnect_all(self):
            self.__slots.clear()
        async def emit_signal(self, *args):
            for slot in self.__slots:
                if slot.is_coroutine:
                    await slot.func(*args)
                else:
                    slot.func(*args)

    def __init__(self, auto_reconnect: bool = True):
        self._access_token = ""
        self._http = None
        self._websocket = None
        self._connected = False
        self._is_simulation = False
        self._last_message = ""
        self._mac_address = None
        self._last_respose_value = None
        self._ws_task = None

        self.connection = ConnectionManager()
        self._reconnector = None
        self._auto_reconnect = auto_reconnect

        self._on_message = self._event_signal()
        self._on_realtime = self._event_signal()

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def is_simulation(self) -> bool:
        return self._is_simulation

    @property
    def last_message(self) -> str:
        return self._last_message

    @property
    def mac_address(self) -> str:
        return self._mac_address

    @mac_address.setter
    def mac_address(self, value):
        self._mac_address = value

    @property
    def on_message(self):
        return self._on_message

    @on_message.setter
    def on_message(self, slot):
        if not hasattr(slot, "__call__"):
            raise ValueError("slot must be callable")
        warnings.warn("use .connect() instead", DeprecationWarning, stacklevel=2)
        self._on_message.connect(slot)

    @property
    def on_realtime(self):
        return self._on_realtime

    @on_realtime.setter
    def on_realtime(self, slot):
        if not hasattr(slot, "__call__"):
            raise ValueError("slot must be callable")
        warnings.warn("use .connect() instead", DeprecationWarning, stacklevel=2)
        self._on_realtime.connect(slot)

    async def close(self):
        if self._reconnector:
            await self._reconnector.stop()
        self.connection.set_state(ConnectionState.CLOSING)
        self._connected = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        if self._websocket and not self._websocket.closed:
            await self._websocket.close()
        if self._http and not self._http.closed:
            await self._http.close()
        self.connection.set_state(ConnectionState.DISCONNECTED)
        self.connection.clear_subscriptions()

    async def login(self, appkey, appsecretkey) -> bool:
        if self._connected:
            self._last_message = "already connected"
            return True
        if not appkey or not appsecretkey:
            self._last_message = "appkey or appsecretkey is empty"
            return False

        self.connection.set_state(ConnectionState.CONNECTING)

        timeout = aiohttp.ClientTimeout(total=10)
        httpclient = aiohttp.ClientSession(timeout=timeout)
        token_response = await httpclient.post(
            BASE_URL + "/oauth2/token",
            data={'grant_type': 'client_credentials', 'appkey': appkey, 'appsecretkey': appsecretkey, 'scope': 'oob'},
        )
        if token_response.status != 200:
            await httpclient.close()
            self._last_message = "Failed to retrieve authentication key."
            self.connection.set_state(ConnectionState.DISCONNECTED)
            return False

        token = (await token_response.json())['access_token']
        httpclient.headers["Authorization"] = f"Bearer {token}"
        httpclient.headers["Content-Type"] = "application/json; charset=UTF-8"
        self._access_token = token
        self._http = httpclient

        FOCCQ33600 = {'FOCCQ33600InBlock1': {}}
        # self.request()는 _connected 게이트가 있어 WS 연결 전(login 중)엔 항상
        # None을 반환한다. 인증된 httpclient로 직접 조회해야 모의투자 판별이 동작한다.
        try:
            async with httpclient.post(
                BASE_URL + "/stock/accno",
                headers={"tr_cd": "FOCCQ33600", "tr_cont": "N", "tr_cont_key": "0"},
                data=json.dumps(FOCCQ33600),
            ) as acc_resp:
                acc_body = json.loads(await acc_resp.text()) if acc_resp.status == 200 else {}
        except aiohttp.ClientError as e:
            logger.warning("계좌 확인(FOCCQ33600) 실패: %s — 실계좌로 간주하고 진행", e)
            acc_body = {}
        if "모의투자" in str(acc_body.get("rsp_msg", "")):
            self._is_simulation = True
            logger.info("모의투자 계정 감지")
        else:
            self._is_simulation = False

        self._connected = False
        try:
            ws_url = WSS_URL_SIMULATION if self._is_simulation else WSS_URL_REAL
            websocket = await httpclient.ws_connect(ws_url)
            self._connected = not websocket.closed
        except Exception as e:
            self._last_message = str(e)

        if not self._connected:
            await httpclient.close()
            self.connection.set_state(ConnectionState.DISCONNECTED)
            return False

        self._websocket = websocket
        self._ws_task = asyncio.create_task(self._websocket_listen())
        self.connection.set_state(ConnectionState.CONNECTED)

        if self._auto_reconnect and not self._reconnector:
            backoff = ExponentialBackoff(initial_delay=2.0, max_delay=30.0)
            self._reconnector = ReconnectionWorker(
                connection_manager=self.connection,
                backoff=backoff,
                on_reconnect=self._reconnect,
                on_resubscribe=self._resubscribe,
            )
            await self._reconnector.start()

        return True

    async def _reconnect(self) -> bool:
        try:
            self._connected = False
            if self._websocket and not self._websocket.closed:
                await self._websocket.close()
            ws_url = WSS_URL_SIMULATION if self._is_simulation else WSS_URL_REAL
            websocket = await self._http.ws_connect(ws_url)
            self._websocket = websocket
            self._connected = not websocket.closed
            if self._connected:
                self._ws_task = asyncio.create_task(self._websocket_listen())
                return True
        except Exception as e:
            self._last_message = str(e)
        return False

    async def _resubscribe(self, subscriptions: list[tuple[str, str]]):
        for tr_code, key in subscriptions:
            try:
                tr_type = "1" if code_realtime_account.__contains__(tr_code) else "3"
                data = f'{{"header":{{"token":"{self._access_token}","tr_type":"{tr_type}"}},"body":{{"tr_cd":"{tr_code}","tr_key":"{key}"}}}}'
                await self._websocket.send_str(data)
                await asyncio.sleep(0.05)
            except Exception as e:
                self._last_message = str(e)

    async def request(self, tr_cd, data, *, path=None, tr_cont="N", tr_cont_key="0"):
        self._last_message = ""
        self._last_respose_value = None
        if not self._connected:
            self._last_message = "Not connected"
            return None
        if not path:
            if tr_cd not in tr_code_to_path:
                self._last_message = "Not supported tr code"
                return None
            path = tr_code_to_path[tr_cd]

        headers = {"tr_cd": tr_cd, "tr_cont": tr_cont, "tr_cont_key": tr_cont_key}
        if self._mac_address:
            headers["mac_address"] = self._mac_address

        try:
            request_text = json.dumps(data) if not isinstance(data, str) else data
            request_time = time.time()
            start_time = time.perf_counter_ns()
            response = await self._http.post(BASE_URL + path, headers=headers, data=request_text)
            if response.status != 200:
                self._last_message = str(await response.json())
                return None
            response_text = await response.text()
            elapsed_ms = (time.perf_counter_ns() - start_time) / 1000000
            result = ResponseValue(path, tr_cd, response.headers.get("tr_cont", "N"), response.headers.get("tr_cont_key", "0"), response_text)
            result.in_tr_cont = tr_cont
            result.in_tr_cont_key = tr_cont_key
            result.request_text = request_text
            result.request_time = request_time
            result.elapsed_ms = elapsed_ms
            self._last_respose_value = result
            return result
        except aiohttp.ClientError as e:
            self._last_message = str(e)
            if self._auto_reconnect and self._reconnector:
                self.connection.set_state(ConnectionState.DISCONNECTED)
                self._reconnector.trigger()
        except Exception as e:
            self._last_message = str(e)
        return None

    def add_realtime(self, tr_cd, tr_key):
        self.connection.add_subscription(tr_cd, tr_key)
        return self._realtime_request(tr_cd, tr_key, "1" if code_realtime_account.__contains__(tr_cd) else "3")

    def remove_realtime(self, tr_cd, tr_key):
        self.connection.remove_subscription(tr_cd, tr_key)
        return self._realtime_request(tr_cd, tr_key, "2" if code_realtime_account.__contains__(tr_cd) else "4")

    async def _websocket_listen(self):
        try:
            async for msg in self._websocket:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        jsondata = json.loads(msg.data)
                    except Exception as e:
                        self._last_message = str(e)
                        await self._inner_on_mesage(f"websocket exception. {e}")
                        continue
                    header = jsondata.get("header")
                    if header:
                        tr_cd = header.get("tr_cd")
                        rsp_msg = header.get("rsp_msg")
                        if rsp_msg:
                            self._last_message = ""
                            tr_type = header.get("tr_type")
                            await self._inner_on_mesage(f"{tr_cd}({tr_type}): {rsp_msg}")
                        body = jsondata.get("body")
                        tr_key = header.get("tr_key")
                        if body is not None:
                            self.connection.record_message(tr_cd, tr_key)
                            await self._inner_on_realtime(tr_cd, tr_key, body)
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    self._last_message = f"websocket closed"
                    await self._inner_on_mesage(f"websocket closed")
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    self._last_message = f"websocket error: {msg}"
                    await self._inner_on_mesage(f"websocket error")
        except asyncio.CancelledError:
            pass
        finally:
            self._connected = False
            self.connection.set_state(ConnectionState.DISCONNECTED)
            if self._auto_reconnect and self._reconnector:
                self._reconnector.trigger()

    def _realtime_request(self, tr_cd, tr_key, tr_type) -> bool:
        if not self._connected:
            self._last_message = "Not connected"
            return False
        data = f'{{"header":{{"token":"{self._access_token}","tr_type":"{tr_type}"}},"body":{{"tr_cd":"{tr_cd}","tr_key":"{tr_key}"}}}}'
        asyncio.ensure_future(self._websocket.send_str(data))
        return True

    async def _inner_on_mesage(self, msg):
        await self._on_message.emit_signal(self, msg)

    async def _inner_on_realtime(self, trcode, key, realtimedata):
        await self._on_realtime.emit_signal(self, trcode, key, realtimedata)
