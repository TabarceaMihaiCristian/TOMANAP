"""Transport-neutral committed domain event contract."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Stable event identity shared by outbox and delivery adapters."""

    id: UUID
    room_code: str
    type: str
    payload: Mapping[str, Any]
    occurred_at: datetime


class EventPublisher(Protocol):
    """Interface implemented by local and future distributed brokers."""

    async def publish_event(self, event: DomainEvent) -> object:
        """Publish one event; duplicates with the same ID are permitted."""
