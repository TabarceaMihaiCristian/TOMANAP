"""Persistence operations for single-use realtime tickets."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RealtimeTicket


class RealtimeTicketRepository:
    """Stage, inspect, and atomically consume hashed handshake tickets."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, ticket: RealtimeTicket) -> RealtimeTicket:
        self.session.add(ticket)
        await self.session.flush()
        return ticket

    async def lock_by_hash(self, ticket_hash: str) -> RealtimeTicket | None:
        statement = (
            select(RealtimeTicket)
            .where(RealtimeTicket.ticket_hash == ticket_hash)
            .with_for_update()
        )
        return await self.session.scalar(statement)

    async def consume_if_available(
        self,
        ticket_id: UUID,
        *,
        consumed_at: datetime,
    ) -> bool:
        """Use an atomic predicate so SQLite also rejects concurrent replay."""
        statement = (
            update(RealtimeTicket)
            .where(
                RealtimeTicket.id == ticket_id,
                RealtimeTicket.consumed_at.is_(None),
                RealtimeTicket.expires_at > consumed_at,
            )
            .values(consumed_at=consumed_at)
            .execution_options(synchronize_session=False)
        )
        result = await self.session.execute(statement)
        return result.rowcount == 1
