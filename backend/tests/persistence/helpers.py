"""Small persistence factories used by focused tests."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Game, Player, Round
from app.models.enums import RoundStatus

NOW = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)


async def create_game(
    session: AsyncSession,
    *,
    room_code: str = "MUNTE7",
) -> Game:
    game = Game(room_code=room_code, round_count=5, round_duration_seconds=60)
    session.add(game)
    await session.flush()
    return game


async def create_player(
    session: AsyncSession,
    game: Game,
    *,
    display_name: str = "Mihai",
    normalized_display_name: str = "mihai",
    seat_number: int = 1,
    is_host: bool = False,
) -> Player:
    player = Player(
        game_id=game.id,
        display_name=display_name,
        normalized_display_name=normalized_display_name,
        seat_number=seat_number,
        is_host=is_host,
    )
    session.add(player)
    await session.flush()
    return player


async def create_round(
    session: AsyncSession,
    game: Game,
    *,
    sequence_number: int = 1,
    letter: str = "P",
    is_current: bool = False,
) -> Round:
    round_record = Round(
        game_id=game.id,
        sequence_number=sequence_number,
        letter=letter,
        is_current=is_current,
        status=RoundStatus.ACTIVE,
        starts_at=NOW,
        ends_at=NOW + timedelta(seconds=60),
    )
    session.add(round_record)
    await session.flush()
    return round_record
