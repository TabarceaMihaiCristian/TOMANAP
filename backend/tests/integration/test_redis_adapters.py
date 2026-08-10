"""Contract tests for distributed Redis adapters."""

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from app.core.events import DomainEvent
from app.db.session import Database
from app.services.readiness import ReadinessService
from app.services.redis_adapters import RedisRateLimiter, RedisRealtimeBroker

pytestmark = pytest.mark.redis


@pytest.fixture
def redis_url() -> str:
    value = os.environ.get("TOMANAP_TEST_REDIS_URL")
    if value is None:
        pytest.skip("TOMANAP_TEST_REDIS_URL is not configured")
    return value


async def test_redis_broker_fans_out_stable_event(redis_url: str) -> None:
    client = Redis.from_url(redis_url, decode_responses=False)
    prefix = f"test:tomanap:{uuid4().hex}"
    broker = RedisRealtimeBroker(client, channel_prefix=prefix)
    event = DomainEvent(
        id=uuid4(),
        room_code="ABC123",
        type="round.closed",
        payload={"round_id": "round-1"},
        occurred_at=datetime(2026, 7, 12, 12, 0, tzinfo=UTC),
    )
    try:
        async with broker.subscribe("ABC123") as queue:
            await broker.publish_event(event)
            received = await asyncio.wait_for(queue.get(), timeout=1)

        assert str(received.id) == str(event.id)
        assert received.type == event.type
        assert received.payload == event.payload
    finally:
        await client.aclose()


async def test_redis_rate_limiter_is_shared_and_atomic(redis_url: str) -> None:
    client = Redis.from_url(redis_url, decode_responses=False)
    prefix = f"test:tomanap:{uuid4().hex}"
    first = RedisRateLimiter(
        client,
        requests=2,
        window_seconds=30,
        key_prefix=prefix,
    )
    second = RedisRateLimiter(
        client,
        requests=2,
        window_seconds=30,
        key_prefix=prefix,
    )
    try:
        decisions = await asyncio.gather(
            first.check("same-client"),
            second.check("same-client"),
            first.check("same-client"),
        )
        assert sum(decision.allowed for decision in decisions) == 2
        denied = next(decision for decision in decisions if not decision.allowed)
        assert denied.retry_after_seconds > 0
    finally:
        keys = [key async for key in client.scan_iter(match=f"{prefix}:*")]
        if keys:
            await client.delete(*keys)
        await client.aclose()


async def test_redis_broker_bounds_a_slow_subscriber_queue(redis_url: str) -> None:
    client = Redis.from_url(redis_url, decode_responses=False)
    prefix = f"test:tomanap:{uuid4().hex}"
    broker = RedisRealtimeBroker(
        client,
        channel_prefix=prefix,
        max_queue_size=2,
    )
    try:
        async with broker.subscribe("ABC123") as queue:
            for index in range(5):
                await broker.publish_event(
                    DomainEvent(
                        id=uuid4(),
                        room_code="ABC123",
                        type="load.event",
                        payload={"index": index},
                        occurred_at=datetime.now(UTC),
                    )
                )
            for _attempt in range(50):
                if queue.qsize() == 2:
                    break
                await asyncio.sleep(0.01)
            received = [queue.get_nowait(), queue.get_nowait()]

        assert [event.payload["index"] for event in received] == [3, 4]
    finally:
        await client.aclose()


async def test_readiness_recovers_after_redis_returns(
    redis_url: str,
    postgres_database: Database,
) -> None:
    client = Redis.from_url(redis_url, decode_responses=False)

    class FaultInjectingRedis:
        failing = True

        async def ping(self) -> bool:
            if self.failing:
                raise ConnectionError("injected Redis outage")
            return bool(await client.ping())

    dependency = FaultInjectingRedis()
    readiness = ReadinessService(
        postgres_database,
        redis=dependency,  # type: ignore[arg-type]
        workers=(),
    )
    try:
        unavailable = await readiness.check(accepting_traffic=True)
        dependency.failing = False
        recovered = await readiness.check(accepting_traffic=True)
    finally:
        await client.aclose()

    assert unavailable.checks["redis"] is False
    assert unavailable.is_ready is False
    assert recovered.checks["redis"] is True
    assert recovered.is_ready is True
