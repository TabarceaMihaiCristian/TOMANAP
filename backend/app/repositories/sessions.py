"""Database access for hashed anonymous sessions."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnonymousSession


class SessionRepository:
    """Read and stage anonymous session rows without committing."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, anonymous_session: AnonymousSession) -> AnonymousSession:
        self.session.add(anonymous_session)
        await self.session.flush()
        return anonymous_session

    async def get_by_id(self, session_id: UUID) -> AnonymousSession | None:
        return await self.session.get(AnonymousSession, session_id)

    async def get_by_session_token_hash(
        self,
        token_hash: str,
    ) -> AnonymousSession | None:
        statement = select(AnonymousSession).where(
            AnonymousSession.session_token_hash == token_hash
        )
        return await self.session.scalar(statement)

    async def get_by_reconnect_token_hash(
        self,
        token_hash: str,
    ) -> AnonymousSession | None:
        statement = select(AnonymousSession).where(
            AnonymousSession.reconnect_token_hash == token_hash
        )
        return await self.session.scalar(statement)

    async def lock_by_reconnect_token_hash(
        self,
        token_hash: str,
    ) -> AnonymousSession | None:
        """Lock a reconnect capability while its hashes are rotated."""
        statement = (
            select(AnonymousSession)
            .where(AnonymousSession.reconnect_token_hash == token_hash)
            .with_for_update()
        )
        return await self.session.scalar(statement)

    async def list_for_player(self, player_id: UUID) -> list[AnonymousSession]:
        statement = select(AnonymousSession).where(
            AnonymousSession.player_id == player_id
        )
        return list((await self.session.scalars(statement)).all())
