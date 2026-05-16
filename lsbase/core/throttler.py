import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """API 호출 제한 초과 시 발생하는 예외"""


class Throttler:
    """Token bucket 기반 API 호출 속도 제한기.

    모든 query/subscribe 호출을 이 throttler를 통과시켜
    API 서버의 호출 제한(1초 N회)을 위반하지 않도록 보장합니다.

    Usage:
        throttler = Throttler(rate=5.0, burst=5)
        await throttler.acquire()  # 허용될 때까지 대기

    Thread-safe for asyncio (단일 이벤트 루프 기준).
    """

    def __init__(self, rate: float = 5.0, burst: int = 5):
        if rate <= 0:
            raise ValueError("rate는 0보다 커야 합니다")
        if burst < 1:
            raise ValueError("burst는 1 이상이어야 합니다")

        self.rate = rate                     # 초당 허용 호출 수
        self.burst = burst                   # 최대 버스트 크기
        self._tokens: float = float(burst)    # 현재 토큰 수
        self._last_refill: float = time.monotonic()
        self._total_acquired: int = 0
        self._total_waited: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> float:
        """토큰을 획득할 때까지 대기. 대기한 시간(초)을 반환."""
        waited = 0.0
        while True:
            wait = self._try_acquire()
            if wait <= 0:
                break
            await asyncio.sleep(min(wait, 0.01))
            waited += wait

        self._total_acquired += 1
        self._total_waited += waited
        return waited

    def _try_acquire(self) -> float:
        """토큰 획득을 시도. 대기해야 하면 필요 대기 시간(초)을 반환."""
        now = time.monotonic()
        elapsed = now - self._last_refill

        # 토큰 리필 (rate tokens per second)
        self._tokens = min(
            float(self.burst),
            self._tokens + elapsed * self.rate,
        )
        self._last_refill = now

        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return 0.0  # 즉시 획득

        # 토큰 부족 — 대기 시간 계산
        return (1.0 - self._tokens) / self.rate

    @property
    def stats(self) -> dict:
        return {
            "rate": self.rate,
            "burst": self.burst,
            "tokens": round(self._tokens, 2),
            "total_calls": self._total_acquired,
            "total_waited_sec": round(self._total_waited, 3),
        }

    def reset(self):
        self._tokens = float(self.burst)
        self._last_refill = time.monotonic()
        self._total_acquired = 0
        self._total_waited = 0.0
