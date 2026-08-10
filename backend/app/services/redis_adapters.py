"""Redis-backed realtime fan-out and distributed abuse protection."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from itertools import count
from uuid import UUID, uuid4

from redis.asyncio import Redis

from app.core.events import DomainEvent
from app.core.rate_limiting import RateLimitDecision
from app.core.security import hash_token
from app.services.realtime import RealtimeEvent

RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local window_ms = tonumber(ARGV[1])
local request_limit = tonumber(ARGV[2])
local member = ARGV[3]
local server_time = redis.call('TIME')
local now_ms = server_time[1] * 1000 + math.floor(server_time[2] / 1000)
redis.call('ZREMRANGEBYSCORE', key, 0, now_ms - window_ms)
local current = redis.call('ZCARD', key)
if current >= request_limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_ms = window_ms
    if oldest[2] then
        retry_ms = math.max(1, window_ms - (now_ms - tonumber(oldest[2])))
    end
    return {0, math.ceil(retry_ms / 1000)}
end
redis.call('ZADD', key, now_ms, member)
redis.call('PEXPIRE', key, window_ms)
return {1, 0}
"""


class RedisRateLimiter:
    """Atomic server-time sliding window shared by every API instance."""

    def __init__(
        self,
        client: Redis,
        *,
        requests: int,
        window_seconds: float,
        key_prefix: str = "tomanap:rate",
    ) -> None:
        if requests < 1 or window_seconds <= 0:
            raise ValueError("Rate-limit bounds must be positive")
        self.client = client
        self.requests = requests
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix.rstrip(":")

    async def check(self, key: str) -> RateLimitDecision:
        redis_key = f"{self.key_prefix}:{hash_token(key)}"
        result = await self.client.eval(
            RATE_LIMIT_SCRIPT,
            1,
            redis_key,
            int(self.window_seconds * 1000),
            self.requests,
            uuid4().hex,
        )
        allowed, retry_after = int(result[0]), int(result[1])
        return RateLimitDecision(bool(allowed), retry_after)


class RedisRealtimeBroker:
    """Redis pub/sub adapter with bounded queues for each local subscriber."""

    def __init__(
        self,
        client: Redis,
        *,
        channel_prefix: str = "tomanap:room",
        max_queue_size: int = 64,
    ) -> None:
        if max_queue_size < 1:
            raise ValueError("max_queue_size must be positive")
        self.client = client
        self.channel_prefix = channel_prefix.rstrip(":")
        self.max_queue_size = max_queue_size
        self._sequence = count(1)

    def _channel(self, room_code: str) -> str:
        return f"{self.channel_prefix}:{room_code.strip().upper()}"

    async def publish_event(self, event: DomainEvent) -> int:
        message = json.dumps(
            {
                "event_id": str(event.id),
                "type": event.type,
                "room_code": event.room_code.strip().upper(),
                "occurred_at": event.occurred_at.isoformat(),
                "payload": dict(event.payload),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return int(await self.client.publish(self._channel(event.room_code), message))

    @asynccontextmanager
    async def subscribe(
        self,
        room_code: str,
    ) -> AsyncIterator[asyncio.Queue[RealtimeEvent]]:
        queue: asyncio.Queue[RealtimeEvent] = asyncio.Queue(maxsize=self.max_queue_size)
        pubsub = self.client.pubsub(ignore_subscribe_messages=True)
        channel = self._channel(room_code)
        await pubsub.subscribe(channel)
        pump = asyncio.create_task(
            self._pump(pubsub, queue),
            name=f"tomanap-redis-room-{room_code.strip().upper()}",
        )
        try:
            yield queue
        finally:
            pump.cancel()
            with suppress(asyncio.CancelledError):
                await pump
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    async def _pump(self, pubsub, queue: asyncio.Queue[RealtimeEvent]) -> None:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            raw = message.get("data")
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            parsed = json.loads(raw)
            event = RealtimeEvent(
                id=(uuid4() if "event_id" not in parsed else UUID(parsed["event_id"])),
                sequence=next(self._sequence),
                type=parsed["type"],
                room_code=parsed["room_code"],
                occurred_at=datetime.fromisoformat(parsed["occurred_at"]),
                payload=parsed["payload"],
            )
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)
