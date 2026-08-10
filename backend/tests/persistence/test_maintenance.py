"""Tests for bounded retention of terminal and expired records."""

from datetime import timedelta

from sqlalchemy import func, select

from app.core.config import Environment, Settings
from app.db.session import Database
from app.models import (
    AnonymousSession,
    Game,
    IdempotencyRecord,
    OutboxEvent,
    RealtimeTicket,
)
from app.models.enums import GameStatus
from app.services.maintenance import MaintenanceService
from tests.persistence.helpers import NOW, create_game, create_player


def _settings(database: Database, *, batch_size: int = 100) -> Settings:
    return Settings(
        _env_file=None,
        environment=Environment.TEST,
        database_url=database.engine.url.render_as_string(hide_password=False),
        maintenance_batch_size=batch_size,
    )


async def test_maintenance_removes_expired_credentials_but_keeps_live_ones(
    database: Database,
) -> None:
    async with database.session() as session:
        game = await create_game(session)
        player = await create_player(session, game)
        session.add_all(
            [
                AnonymousSession(
                    player_id=player.id,
                    session_token_hash="a" * 64,
                    reconnect_token_hash="b" * 64,
                    expires_at=NOW - timedelta(days=2),
                    reconnect_expires_at=NOW - timedelta(seconds=1),
                ),
                AnonymousSession(
                    player_id=player.id,
                    session_token_hash="c" * 64,
                    reconnect_token_hash="d" * 64,
                    expires_at=NOW + timedelta(hours=1),
                    reconnect_expires_at=NOW + timedelta(days=1),
                ),
                RealtimeTicket(
                    game_id=game.id,
                    player_id=player.id,
                    ticket_hash="e" * 64,
                    expires_at=NOW - timedelta(seconds=1),
                ),
                RealtimeTicket(
                    game_id=game.id,
                    player_id=player.id,
                    ticket_hash="f" * 64,
                    expires_at=NOW + timedelta(seconds=30),
                ),
                IdempotencyRecord(
                    player_id=player.id,
                    operation="game:start",
                    key_hash="1" * 64,
                    request_hash="2" * 64,
                    expires_at=NOW - timedelta(seconds=1),
                ),
                IdempotencyRecord(
                    player_id=player.id,
                    operation="round:advance",
                    key_hash="3" * 64,
                    request_hash="4" * 64,
                    expires_at=NOW + timedelta(hours=1),
                ),
            ]
        )
        await session.commit()

    result = await MaintenanceService(database, _settings(database)).run_once(now=NOW)

    assert result.sessions == 1
    assert result.realtime_tickets == 1
    assert result.idempotency_records == 1
    async with database.session() as session:
        assert await session.scalar(select(func.count(AnonymousSession.id))) == 1
        assert await session.scalar(select(func.count(RealtimeTicket.id))) == 1
        assert await session.scalar(select(func.count(IdempotencyRecord.id))) == 1


async def test_maintenance_is_bounded_and_preserves_pending_outbox(
    database: Database,
) -> None:
    async with database.session() as session:
        session.add_all(
            OutboxEvent(
                room_code="ABC123",
                event_type=f"test.old_{index}",
                payload={},
                occurred_at=NOW - timedelta(days=8),
                available_at=NOW - timedelta(days=8),
                published_at=NOW - timedelta(days=8),
            )
            for index in range(3)
        )
        session.add(
            OutboxEvent(
                room_code="ABC123",
                event_type="test.pending",
                payload={},
                occurred_at=NOW - timedelta(days=8),
                available_at=NOW - timedelta(days=8),
            )
        )
        await session.commit()

    service = MaintenanceService(database, _settings(database, batch_size=2))
    first = await service.run_once(now=NOW)
    second = await service.run_once(now=NOW)

    assert first.outbox_events == 2
    assert second.outbox_events == 1
    async with database.session() as session:
        remaining = list((await session.scalars(select(OutboxEvent.event_type))).all())
    assert remaining == ["test.pending"]


async def test_maintenance_deletes_only_old_terminal_games(
    database: Database,
) -> None:
    async with database.session() as session:
        expired = await create_game(session, room_code="OLD001")
        expired.status = GameStatus.COMPLETED
        expired.completed_at = NOW - timedelta(days=31)
        recent = await create_game(session, room_code="NEW001")
        recent.status = GameStatus.COMPLETED
        recent.completed_at = NOW - timedelta(days=1)
        active = await create_game(session, room_code="PLAY01")
        active.status = GameStatus.IN_PROGRESS
        await session.commit()

    result = await MaintenanceService(database, _settings(database)).run_once(now=NOW)

    assert result.games == 1
    async with database.session() as session:
        room_codes = set((await session.scalars(select(Game.room_code))).all())
    assert room_codes == {"NEW001", "PLAY01"}
