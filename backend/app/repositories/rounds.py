"""Database access for authoritative rounds."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Round
from app.models.enums import RoundStatus


class RoundRepository:
    """Read and stage round rows without committing transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, round_record: Round) -> Round:
        self.session.add(round_record)
        await self.session.flush()
        return round_record

    async def get_by_id(self, round_id: UUID) -> Round | None:
        return await self.session.get(Round, round_id)

    async def lock_by_id(self, round_id: UUID) -> Round | None:
        statement = (
            select(Round)
            .where(Round.id == round_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(statement)

    async def get_current_for_game(self, game_id: UUID) -> Round | None:
        statement = select(Round).where(
            Round.game_id == game_id,
            Round.is_current.is_(True),
        )
        return await self.session.scalar(statement)

    async def lock_current_for_game(self, game_id: UUID) -> Round | None:
        statement = (
            select(Round)
            .where(
                Round.game_id == game_id,
                Round.is_current.is_(True),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(statement)

    async def list_used_letters(self, game_id: UUID) -> list[str]:
        statement = (
            select(Round.letter)
            .where(Round.game_id == game_id)
            .order_by(Round.sequence_number)
        )
        return list((await self.session.scalars(statement)).all())

    async def list_due_ids(
        self,
        checked_at: datetime,
        *,
        limit: int,
    ) -> list[UUID]:
        """Return a bounded batch of potentially expired active rounds."""
        statement = (
            select(Round.id)
            .where(
                Round.status == RoundStatus.ACTIVE,
                Round.scored_at.is_(None),
                Round.ends_at.is_not(None),
                Round.ends_at <= checked_at,
            )
            .order_by(Round.ends_at, Round.id)
            .limit(limit)
        )
        return list((await self.session.scalars(statement)).all())
