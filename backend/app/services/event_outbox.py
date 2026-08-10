"""Transaction-bound staging of JSON-safe domain events."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic_core import to_jsonable_python
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OutboxEvent
from app.repositories.outbox import OutboxRepository
from app.utilities.datetime import utc_now


class EventOutbox:
    """Stage events in the caller's existing domain transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = OutboxRepository(session)

    async def stage(
        self,
        room_code: str,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        occurred_at: datetime | None = None,
    ) -> OutboxEvent:
        """Persist one event without committing the caller's transaction."""
        timestamp = occurred_at or utc_now()
        json_payload = to_jsonable_python(dict(payload))
        if not isinstance(json_payload, dict):
            raise TypeError("Outbox payload must serialize to an object")
        return await self.repository.add(
            OutboxEvent(
                room_code=room_code.strip().upper(),
                event_type=event_type,
                payload=json_payload,
                occurred_at=timestamp,
                available_at=timestamp,
            )
        )
