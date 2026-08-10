"""Bounded, room-scoped realtime event distribution."""

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from itertools import count
from typing import Any
from uuid import UUID, uuid4

from app.core.events import DomainEvent
from app.utilities.datetime import utc_now


@dataclass(frozen=True, slots=True)
class RealtimeEvent:
    """Token-free event sent to every subscriber in one room."""

    id: UUID
    sequence: int
    type: str
    room_code: str
    occurred_at: datetime
    payload: Mapping[str, Any]

    def as_message(self) -> dict[str, Any]:
        """Return a JSON-compatible WebSocket message."""
        return {
            "event_id": str(self.id),
            "sequence": self.sequence,
            "type": self.type,
            "room_code": self.room_code,
            "occurred_at": self.occurred_at.isoformat().replace("+00:00", "Z"),
            "payload": dict(self.payload),
        }


class RealtimeBroker:
    """Fan out events without allowing slow clients to block producers."""

    def __init__(self, *, max_queue_size: int = 64) -> None:
        if max_queue_size < 1:
            raise ValueError("max_queue_size must be positive")
        self.max_queue_size = max_queue_size
        self._subscribers: dict[str, set[asyncio.Queue[RealtimeEvent]]] = defaultdict(
            set
        )
        self._sequence = count(1)

    @staticmethod
    def _room_code(room_code: str) -> str:
        return room_code.strip().upper()

    @asynccontextmanager
    async def subscribe(
        self,
        room_code: str,
    ) -> AsyncIterator[asyncio.Queue[RealtimeEvent]]:
        """Register a bounded queue for the duration of a connection."""
        normalized = self._room_code(room_code)
        queue: asyncio.Queue[RealtimeEvent] = asyncio.Queue(maxsize=self.max_queue_size)
        self._subscribers[normalized].add(queue)
        try:
            yield queue
        finally:
            subscribers = self._subscribers.get(normalized)
            if subscribers is not None:
                subscribers.discard(queue)
                if not subscribers:
                    self._subscribers.pop(normalized, None)

    async def publish(
        self,
        room_code: str,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        occurred_at: datetime | None = None,
        event_id: UUID | None = None,
    ) -> RealtimeEvent:
        """Publish immediately, dropping each slow subscriber's oldest event."""
        normalized = self._room_code(room_code)
        event = RealtimeEvent(
            id=event_id or uuid4(),
            sequence=next(self._sequence),
            type=event_type,
            room_code=normalized,
            occurred_at=occurred_at or utc_now(),
            payload=dict(payload),
        )
        for queue in tuple(self._subscribers.get(normalized, ())):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)
        return event

    async def publish_event(self, event: DomainEvent) -> RealtimeEvent:
        """Deliver one stable outbox event to local room subscribers."""
        return await self.publish(
            event.room_code,
            event.type,
            event.payload,
            occurred_at=event.occurred_at,
            event_id=event.id,
        )

    def subscriber_count(self, room_code: str) -> int:
        """Expose aggregate connection count without subscriber identities."""
        return len(self._subscribers.get(self._room_code(room_code), ()))
