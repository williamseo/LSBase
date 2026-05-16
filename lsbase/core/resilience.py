import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSING = "closing"


@dataclass
class SubscriptionState:
    tr_code: str
    key: str
    subscribed_at: float = field(default_factory=time.time)
    last_message_at: Optional[float] = None
    message_count: int = 0

    def record_message(self):
        self.last_message_at = time.time()
        self.message_count += 1


class ConnectionManager:
    def __init__(self):
        self._state = ConnectionState.DISCONNECTED
        self._subscriptions: dict[tuple[str, str], SubscriptionState] = {}
        self._reconnect_count = 0
        self._last_disconnect_time: Optional[float] = None
        self._last_connect_time: Optional[float] = None
        self._total_uptime: float = 0.0
        self._connect_start_time: Optional[float] = None

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED

    def set_state(self, state: ConnectionState):
        old = self._state
        self._state = state
        if state == ConnectionState.CONNECTED:
            self._last_connect_time = time.time()
            self._connect_start_time = time.time()
            if old == ConnectionState.RECONNECTING:
                self._reconnect_count += 1
                logger.info("connection_restored, reconnect_count=%d", self._reconnect_count)
        elif state == ConnectionState.DISCONNECTED:
            self._last_disconnect_time = time.time()
            if self._connect_start_time:
                self._total_uptime += time.time() - self._connect_start_time
                self._connect_start_time = None
            logger.info("connection_disconnected")

    def add_subscription(self, tr_code: str, key: str):
        sk = (tr_code, key)
        if sk not in self._subscriptions:
            self._subscriptions[sk] = SubscriptionState(tr_code=tr_code, key=key)

    def remove_subscription(self, tr_code: str, key: str):
        self._subscriptions.pop((tr_code, key), None)

    def record_message(self, tr_code: str, key: str):
        sk = (tr_code, key)
        if sk in self._subscriptions:
            self._subscriptions[sk].record_message()

    def get_all_subscriptions(self) -> list[tuple[str, str]]:
        return [(s.tr_code, s.key) for s in self._subscriptions.values()]

    def clear_subscriptions(self):
        self._subscriptions.clear()

    @property
    def subscription_count(self) -> int:
        return len(self._subscriptions)

    def get_stats(self) -> dict:
        uptime = self._total_uptime
        if self._connect_start_time:
            uptime += time.time() - self._connect_start_time
        return {
            "state": self._state.value,
            "subscriptions": self.subscription_count,
            "reconnects": self._reconnect_count,
            "uptime_sec": round(uptime, 1),
        }


class ExponentialBackoff:
    def __init__(self, initial_delay: float = 1.0, max_delay: float = 30.0, multiplier: float = 2.0):
        self._initial = initial_delay
        self._max = max_delay
        self._mult = multiplier
        self._current = initial_delay
        self._attempt = 0

    def next_delay(self) -> float:
        delay = self._current
        self._attempt += 1
        self._current = min(self._current * self._mult, self._max)
        return delay

    def reset(self):
        self._current = self._initial
        self._attempt = 0

    @property
    def attempt(self) -> int:
        return self._attempt


class ReconnectionWorker:
    def __init__(
        self,
        connection_manager: ConnectionManager,
        backoff: ExponentialBackoff,
        on_reconnect: Callable[[], asyncio.Future],
        on_resubscribe: Callable[[list[tuple[str, str]]], asyncio.Future],
        max_attempts: int = 0,
    ):
        self._cm = connection_manager
        self._backoff = backoff
        self._on_reconnect = on_reconnect
        self._on_resubscribe = on_resubscribe
        self._max_attempts = max_attempts
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._trigger = asyncio.Event()

    def trigger(self):
        if self._running:
            self._trigger.set()

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._running = False
        self._trigger.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self):
        while self._running:
            try:
                await self._trigger.wait()
                self._trigger.clear()
                if not self._running:
                    break

                self._cm.set_state(ConnectionState.RECONNECTING)
                subs = self._cm.get_all_subscriptions()
                logger.info("reconnect starting, %d subscriptions", len(subs))

                success = False
                while self._running:
                    if self._max_attempts > 0 and self._backoff.attempt >= self._max_attempts:
                        logger.error("reconnect max attempts reached")
                        break
                    delay = self._backoff.next_delay()
                    logger.info("reconnect waiting %.1fs (attempt %d)", delay, self._backoff.attempt)
                    await asyncio.sleep(delay)
                    if not self._running:
                        break
                    try:
                        success = await self._on_reconnect()
                    except Exception as e:
                        logger.error("reconnect failed: %s", e)
                        success = False
                    if success:
                        self._backoff.reset()
                        self._cm.set_state(ConnectionState.CONNECTED)
                        break

                if success and subs and self._running:
                    logger.info("resubscribing %d TRs", len(subs))
                    try:
                        await self._on_resubscribe(subs)
                    except Exception as e:
                        logger.error("resubscribe error: %s", e)

            except asyncio.CancelledError:
                break
