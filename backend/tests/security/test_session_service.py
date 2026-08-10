"""Tests for anonymous session expiry and hash-only persistence."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Environment, Settings
from app.core.exceptions import InvalidSessionError
from app.db.base import Base
from app.db.session import Database
from app.models import Game, Player
from app.services.sessions import AnonymousSessionService

NOW = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)


@pytest_asyncio.fixture
async def session_service(
    tmp_path: Path,
) -> AsyncIterator[tuple[AnonymousSessionService, AsyncSession, UUID]]:
    database_path = (tmp_path / "sessions.db").as_posix()
    settings = Settings(
        _env_file=None,
        environment=Environment.TEST,
        database_url=f"sqlite+aiosqlite:///{database_path}",
    )
    database = Database(settings.database_url)
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.session() as session:
        async with session.begin():
            game = Game(room_code="ABC234")
            session.add(game)
            await session.flush()
            player = Player(
                game_id=game.id,
                display_name="Ana",
                normalized_display_name="ana",
                seat_number=1,
                is_host=True,
            )
            session.add(player)
            await session.flush()
        service = AnonymousSessionService(session, settings)
        yield service, session, player.id
        await session.rollback()
    await database.dispose()


async def test_session_persists_only_hashes_and_expires_authorization(
    session_service: tuple[AnonymousSessionService, AsyncSession, UUID],
) -> None:
    service, session, player_id = session_service
    async with session.begin():
        record, tokens = await service.issue_for_player(player_id, now=NOW)

    assert record.session_token_hash != tokens.session_token
    assert record.reconnect_token_hash != tokens.reconnect_token
    assert len(record.session_token_hash) == 64
    assert (await service.authenticate(tokens.session_token, now=NOW)).player.id == (
        player_id
    )

    with pytest.raises(InvalidSessionError):
        await service.authenticate(
            tokens.session_token,
            now=NOW + timedelta(minutes=121),
        )


async def test_expired_reconnect_token_cannot_be_rotated(
    session_service: tuple[AnonymousSessionService, AsyncSession, UUID],
) -> None:
    service, session, player_id = session_service
    async with session.begin():
        _record, tokens = await service.issue_for_player(player_id, now=NOW)

    with pytest.raises(InvalidSessionError):
        await service.restore(
            tokens.reconnect_token,
            now=NOW + timedelta(days=8),
        )
