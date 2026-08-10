"""Database access for anonymous player memberships."""

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Player


class PlayerRepository:
    """Read and stage player rows without committing transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, player: Player) -> Player:
        self.session.add(player)
        await self.session.flush()
        return player

    async def get_by_id(self, player_id: UUID) -> Player | None:
        return await self.session.get(Player, player_id)

    async def list_for_game(
        self,
        game_id: UUID,
        *,
        active_only: bool = True,
    ) -> list[Player]:
        statement = select(Player).where(Player.game_id == game_id)
        if active_only:
            statement = statement.where(Player.is_active.is_(True))
        statement = statement.order_by(Player.seat_number)
        return list((await self.session.scalars(statement)).all())

    async def normalized_name_exists(
        self,
        game_id: UUID,
        normalized_name: str,
    ) -> bool:
        statement = select(
            exists().where(
                Player.game_id == game_id,
                Player.normalized_display_name == normalized_name,
                Player.is_active.is_(True),
            )
        )
        return bool(await self.session.scalar(statement))

    async def get_host(self, game_id: UUID) -> Player | None:
        statement = select(Player).where(
            Player.game_id == game_id,
            Player.is_host.is_(True),
            Player.is_active.is_(True),
        )
        return await self.session.scalar(statement)
