"""Database access for score records and leaderboard aggregation."""

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Player, Score


@dataclass(frozen=True, slots=True)
class LeaderboardRow:
    """Repository-level leaderboard projection."""

    player_id: UUID
    display_name: str
    seat_number: int
    total_score: int


class ScoreRepository:
    """Read and stage scores without committing transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_all(self, scores: Iterable[Score]) -> list[Score]:
        materialized = list(scores)
        self.session.add_all(materialized)
        await self.session.flush()
        return materialized

    async def get_round_scores(self, round_id: UUID) -> list[Score]:
        statement = (
            select(Score)
            .where(Score.round_id == round_id)
            .order_by(Score.player_id, Score.category)
        )
        return list((await self.session.scalars(statement)).all())

    async def get_leaderboard(self, game_id: UUID) -> list[LeaderboardRow]:
        total_score = func.coalesce(func.sum(Score.points), 0).label("total_score")
        statement = (
            select(
                Player.id,
                Player.display_name,
                Player.seat_number,
                total_score,
            )
            .outerjoin(Score, Score.player_id == Player.id)
            .where(Player.game_id == game_id, Player.is_active.is_(True))
            .group_by(Player.id, Player.display_name, Player.seat_number)
            .order_by(total_score.desc(), Player.seat_number)
        )
        rows = (await self.session.execute(statement)).all()
        return [
            LeaderboardRow(
                player_id=row.id,
                display_name=row.display_name,
                seat_number=row.seat_number,
                total_score=int(row.total_score),
            )
            for row in rows
        ]
