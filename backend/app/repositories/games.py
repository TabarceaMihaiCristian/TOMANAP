"""Database access for persisted TOMANAP games."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Game


class GameRepository:
    """Read and stage game rows without owning transaction commits."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, game: Game) -> Game:
        self.session.add(game)
        await self.session.flush()
        return game

    async def get_by_id(self, game_id: UUID) -> Game | None:
        return await self.session.get(Game, game_id)

    async def lock_by_id(self, game_id: UUID) -> Game | None:
        statement = (
            select(Game)
            .where(Game.id == game_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(statement)

    async def get_by_room_code(self, room_code: str) -> Game | None:
        statement = select(Game).where(Game.room_code == room_code.strip().upper())
        return await self.session.scalar(statement)

    async def lock_by_room_code(self, room_code: str) -> Game | None:
        """Lock a room row for a service-owned state transition."""
        statement = (
            select(Game)
            .where(Game.room_code == room_code.strip().upper())
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(statement)
