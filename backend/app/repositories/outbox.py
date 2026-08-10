"""Transaction-neutral access to durable outbox events."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OutboxEvent


class OutboxRepository:
    """Stage, lease, and settle at-least-once domain events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, event: OutboxEvent) -> OutboxEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_latest_for_room(self, room_code: str) -> OutboxEvent | None:
        """Return the newest durable marker used by reconnect snapshots."""
        statement = (
            select(OutboxEvent)
            .where(OutboxEvent.room_code == room_code.strip().upper())
            .order_by(
                OutboxEvent.occurred_at.desc(),
                OutboxEvent.created_at.desc(),
                OutboxEvent.id.desc(),
            )
            .limit(1)
        )
        return await self.session.scalar(statement)

    async def claim_batch(
        self,
        checked_at: datetime,
        *,
        limit: int,
        lease_seconds: float,
    ) -> list[OutboxEvent]:
        """Lease due rows, skipping rows held by another PostgreSQL worker."""
        if limit < 1 or lease_seconds <= 0:
            raise ValueError("Outbox claim bounds must be positive")
        expired_before = checked_at - timedelta(seconds=lease_seconds)
        statement = (
            select(OutboxEvent)
            .where(
                OutboxEvent.published_at.is_(None),
                OutboxEvent.available_at <= checked_at,
                or_(
                    OutboxEvent.claimed_at.is_(None),
                    OutboxEvent.claimed_at <= expired_before,
                ),
            )
            .order_by(OutboxEvent.occurred_at, OutboxEvent.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        events = list((await self.session.scalars(statement)).all())
        for event in events:
            event.claimed_at = checked_at
            event.claim_token = uuid4()
            event.attempts += 1
        await self.session.flush()
        return events

    async def mark_published(
        self,
        event_id: UUID,
        claim_token: UUID | None,
        *,
        published_at: datetime,
    ) -> bool:
        """Settle only the worker that still owns the current lease."""
        event = await self._lock_owned(event_id, claim_token)
        if event is None:
            return False
        event.published_at = published_at
        event.claimed_at = None
        event.claim_token = None
        event.last_error = None
        await self.session.flush()
        return True

    async def mark_failed(
        self,
        event_id: UUID,
        claim_token: UUID | None,
        *,
        available_at: datetime,
        error: str,
    ) -> bool:
        """Release an owned lease and make the event available for retry."""
        event = await self._lock_owned(event_id, claim_token)
        if event is None:
            return False
        event.available_at = available_at
        event.claimed_at = None
        event.claim_token = None
        event.last_error = error[:500]
        await self.session.flush()
        return True

    async def _lock_owned(
        self,
        event_id: UUID,
        claim_token: UUID | None,
    ) -> OutboxEvent | None:
        if claim_token is None:
            return None
        statement = (
            select(OutboxEvent)
            .where(
                OutboxEvent.id == event_id,
                OutboxEvent.claim_token == claim_token,
                OutboxEvent.published_at.is_(None),
            )
            .with_for_update()
        )
        return await self.session.scalar(statement)
