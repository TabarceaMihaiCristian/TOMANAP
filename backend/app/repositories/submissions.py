"""Database access for draft and finalized submissions."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Submission


class SubmissionRepository:
    """Read and stage submission rows without committing transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, submission: Submission) -> Submission:
        self.session.add(submission)
        await self.session.flush()
        return submission

    async def get_for_player_round(
        self,
        player_id: UUID,
        round_id: UUID,
    ) -> Submission | None:
        statement = select(Submission).where(
            Submission.player_id == player_id,
            Submission.round_id == round_id,
        )
        return await self.session.scalar(statement)

    async def lock_for_player_round(
        self,
        player_id: UUID,
        round_id: UUID,
    ) -> Submission | None:
        statement = (
            select(Submission)
            .where(
                Submission.player_id == player_id,
                Submission.round_id == round_id,
            )
            .with_for_update()
        )
        return await self.session.scalar(statement)

    async def list_for_round(self, round_id: UUID) -> list[Submission]:
        statement = select(Submission).where(Submission.round_id == round_id)
        return list((await self.session.scalars(statement)).all())
