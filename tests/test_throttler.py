import sys
sys.path.insert(0, '.')

import asyncio
import pytest
from lsbase.core.throttler import Throttler


class TestThrottler:
    @pytest.mark.asyncio
    async def test_burst_immediate(self):
        t = Throttler(rate=10.0, burst=5)
        t0 = asyncio.get_event_loop().time()
        for _ in range(5):
            await t.acquire()
        elapsed = asyncio.get_event_loop().time() - t0
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        t = Throttler(rate=10.0, burst=1)
        t0 = asyncio.get_event_loop().time()
        for _ in range(3):
            await t.acquire()
        elapsed = asyncio.get_event_loop().time() - t0
        assert elapsed >= 0.15

    @pytest.mark.asyncio
    async def test_stats(self):
        t = Throttler(rate=5.0, burst=2)
        await t.acquire()
        stats = t.stats
        assert stats["rate"] == 5.0
        assert stats["burst"] == 2
        assert stats["total_calls"] == 1

    @pytest.mark.asyncio
    async def test_reset(self):
        t = Throttler(rate=5.0, burst=3)
        for _ in range(6):
            await t.acquire()
        t.reset()
        assert t.stats["total_calls"] == 0
        assert t.stats["tokens"] == 3.0

    def test_invalid_rate(self):
        with pytest.raises(ValueError):
            Throttler(rate=0)

    def test_invalid_burst(self):
        with pytest.raises(ValueError):
            Throttler(rate=5.0, burst=0)

    @pytest.mark.asyncio
    async def test_exact_rate(self):
        t = Throttler(rate=5.0, burst=5)
        t0 = asyncio.get_event_loop().time()
        for _ in range(5):
            await t.acquire()
        elapsed = asyncio.get_event_loop().time() - t0
        assert elapsed < 0.1
