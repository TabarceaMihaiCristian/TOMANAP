"""Persistence operations for scoped idempotency responses."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IdempotencyRecord


class IdempotencyRepository:
    """Read and stage command records without owning transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, record: IdempotencyRecord) -> IdempotencyRecord:
        self.session.add(record)
        await self.session.flush()
        return record

    async def lock(
        self,
        player_id: UUID,
        operation: str,
        key_hash: str,
    ) -> IdempotencyRecord | None:
        statement = (
            select(IdempotencyRecord)
            .where(
                IdempotencyRecord.player_id == player_id,
                IdempotencyRecord.operation == operation,
                IdempotencyRecord.key_hash == key_hash,
            )
            .with_for_update()
        )
        return await self.session.scalar(statement)

    async def delete(self, record: IdempotencyRecord) -> None:
        await self.session.delete(record)
        await self.session.flush()
