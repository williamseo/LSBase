import sys
sys.path.insert(0, '.')

import asyncio
import pytest
from lsbase.core.resilience import (
    ConnectionManager, ConnectionState, ExponentialBackoff, ReconnectionWorker,
)


class TestConnectionManager:
    def test_initial_state(self):
        cm = ConnectionManager()
        assert cm.state == ConnectionState.DISCONNECTED
        assert cm.is_connected is False

    def test_state_transitions(self):
        cm = ConnectionManager()
        cm.set_state(ConnectionState.CONNECTED)
        assert cm.is_connected is True
        cm.set_state(ConnectionState.DISCONNECTED)
        assert cm.is_connected is False

    def test_subscription_tracking(self):
        cm = ConnectionManager()
        cm.add_subscription("S3_", "005930")
        cm.add_subscription("H1_", "005930")
        assert cm.subscription_count == 2
        cm.add_subscription("S3_", "005930")  # duplicate
        assert cm.subscription_count == 2
        cm.remove_subscription("S3_", "005930")
        assert cm.subscription_count == 1
        subs = cm.get_all_subscriptions()
        assert ("H1_", "005930") in subs

    def test_record_message(self):
        cm = ConnectionManager()
        cm.add_subscription("S3_", "005930")
        cm.record_message("S3_", "005930")
        cm.record_message("S3_", "005930")
        _, state = list(cm._subscriptions.items())[0]
        assert state.message_count == 2

    def test_clear_subscriptions(self):
        cm = ConnectionManager()
        cm.add_subscription("S3_", "005930")
        cm.clear_subscriptions()
        assert cm.subscription_count == 0

    def test_stats(self):
        cm = ConnectionManager()
        cm.add_subscription("S3_", "005930")
        stats = cm.get_stats()
        assert "state" in stats
        assert stats["subscriptions"] == 1


class TestExponentialBackoff:
    def test_delays(self):
        b = ExponentialBackoff(initial_delay=0.1, max_delay=1.0)
        assert b.next_delay() == 0.1
        assert b.next_delay() == 0.2
        assert b.next_delay() == 0.4
        assert b.next_delay() == 0.8
        assert b.next_delay() == 1.0
        assert b.next_delay() == 1.0  # capped

    def test_reset(self):
        b = ExponentialBackoff(initial_delay=1.0, max_delay=5.0)
        b.next_delay()
        b.next_delay()
        b.reset()
        assert b.attempt == 0
        assert b.next_delay() == 1.0


class TestReconnectionWorker:
    @pytest.mark.asyncio
    async def test_reconnect_flow(self):
        cm = ConnectionManager()
        cm.add_subscription("S3_", "005930")
        cm.set_state(ConnectionState.CONNECTED)

        attempts = 0
        async def on_reconnect():
            nonlocal attempts
            attempts += 1
            return attempts >= 2

        resubscribed = []
        async def on_resubscribe(subs):
            resubscribed.extend(subs)

        worker = ReconnectionWorker(
            connection_manager=cm,
            backoff=ExponentialBackoff(initial_delay=0.05, max_delay=0.1),
            on_reconnect=on_reconnect,
            on_resubscribe=on_resubscribe,
        )
        await worker.start()
        worker.trigger()
        await asyncio.sleep(0.3)
        await worker.stop()

        assert attempts >= 1
        assert len(resubscribed) > 0
