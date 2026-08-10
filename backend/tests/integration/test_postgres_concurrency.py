"""Cross-instance correctness tests against production PostgreSQL semantics."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import func, select, text

from app.core.config import Environment, Settings
from app.core.events import DomainEvent
from app.db.session import Database
from app.models import Game, OutboxEvent, Player, Round, Score
from app.models.enums import GameStatus, RoundStatus
from app.repositories.outbox import OutboxRepository
from app.services.maintenance import MaintenanceService
from app.services.outbox import OutboxDispatcher
from app.services.timers import DeadlineSweeper
from tests.persistence.helpers import NOW

pytestmark = pytest.mark.postgres


class RecordingPublisher:
    """Collect events published by one simulated application instance."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    async def publish_event(self, event: DomainEvent) -> None:
        self.events.append(event)


def _settings(database_url: str, **updates: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "environment": Environment.TEST,
        "database_url": database_url,
        "cors_origins": ("https://game.example.test",),
        "allowed_hosts": ("testserver",),
    }
    values.update(updates)
    return Settings(**values)


def _dispatcher(database: Database, publisher: RecordingPublisher) -> OutboxDispatcher:
    return OutboxDispatcher(
        database,
        publisher,
        batch_size=10,
        lease_seconds=30,
        retry_base_seconds=1,
        retry_max_seconds=10,
    )


async def test_postgres_is_migrated_to_the_application_head(
    postgres_database: Database,
) -> None:
    async with postgres_database.session() as session:
        revision = await session.scalar(text("SELECT version_num FROM alembic_version"))

    assert revision == "d19f3b72a451"


async def test_two_dispatchers_lease_each_outbox_event_once(
    postgres_database: Database,
    postgres_url: str,
) -> None:
    async with postgres_database.session() as session:
        async with session.begin():
            repository = OutboxRepository(session)
            for index in range(20):
                await repository.add(
                    OutboxEvent(
                        room_code="ABC123",
                        event_type="load.event",
                        payload={"index": index},
                        occurred_at=NOW + timedelta(microseconds=index),
                        available_at=NOW,
                    )
                )

    second_database = Database(postgres_url)
    first_publisher = RecordingPublisher()
    second_publisher = RecordingPublisher()
    try:
        results = await asyncio.gather(
            _dispatcher(postgres_database, first_publisher).dispatch_once(now=NOW),
            _dispatcher(second_database, second_publisher).dispatch_once(now=NOW),
        )
    finally:
        await second_database.dispose()

    events = first_publisher.events + second_publisher.events
    assert sum(result.claimed for result in results) == 20
    assert sum(result.published for result in results) == 20
    assert len({event.id for event in events}) == 20
    async with postgres_database.session() as session:
        published = await session.scalar(
            select(func.count(OutboxEvent.id)).where(
                OutboxEvent.published_at.is_not(None)
            )
        )
    assert published == 20


async def test_two_deadline_sweepers_finalize_and_score_once(
    postgres_database: Database,
    postgres_url: str,
) -> None:
    async with postgres_database.session() as session:
        async with session.begin():
            game = Game(
                room_code="RACE01",
                status=GameStatus.IN_PROGRESS,
                round_count=1,
                round_duration_seconds=60,
                started_at=NOW - timedelta(minutes=2),
            )
            session.add(game)
            await session.flush()
            session.add_all(
                [
                    Player(
                        game_id=game.id,
                        display_name="Mihai",
                        normalized_display_name="mihai",
                        seat_number=1,
                        is_host=True,
                    ),
                    Player(
                        game_id=game.id,
                        display_name="Ana",
                        normalized_display_name="ana",
                        seat_number=2,
                    ),
                    Round(
                        game_id=game.id,
                        sequence_number=1,
                        letter="P",
                        status=RoundStatus.ACTIVE,
                        is_current=True,
                        starts_at=NOW - timedelta(minutes=2),
                        ends_at=NOW - timedelta(minutes=1),
                    ),
                ]
            )

    second_database = Database(postgres_url)
    settings = _settings(postgres_url)
    first_publisher = RecordingPublisher()
    second_publisher = RecordingPublisher()
    first = DeadlineSweeper(
        postgres_database,
        settings,
        _dispatcher(postgres_database, first_publisher),
    )
    second = DeadlineSweeper(
        second_database,
        settings,
        _dispatcher(second_database, second_publisher),
    )
    try:
        closures = await asyncio.gather(first.sweep_once(), second.sweep_once())
    finally:
        await second_database.dispose()

    assert sorted(closures) == [0, 1]
    async with postgres_database.session() as session:
        score_count = await session.scalar(select(func.count(Score.id)))
        scored_rounds = await session.scalar(
            select(func.count(Round.id)).where(Round.scored_at.is_not(None))
        )
    events = first_publisher.events + second_publisher.events
    assert score_count == 14
    assert scored_rounds == 1
    assert sum(event.type == "round.closed" for event in events) == 1


async def test_two_maintenance_instances_delete_disjoint_batches(
    postgres_database: Database,
    postgres_url: str,
) -> None:
    async with postgres_database.session() as session:
        async with session.begin():
            session.add_all(
                OutboxEvent(
                    room_code="ABC123",
                    event_type="old.event",
                    payload={"index": index},
                    occurred_at=NOW - timedelta(days=8),
                    available_at=NOW - timedelta(days=8),
                    published_at=NOW - timedelta(days=8),
                )
                for index in range(8)
            )

    settings = _settings(postgres_url, maintenance_batch_size=4)
    second_database = Database(postgres_url)
    try:
        results = await asyncio.gather(
            MaintenanceService(postgres_database, settings).run_once(now=NOW),
            MaintenanceService(second_database, settings).run_once(now=NOW),
        )
    finally:
        await second_database.dispose()

    assert sum(result.outbox_events for result in results) == 8
    async with postgres_database.session() as session:
        remaining = await session.scalar(select(func.count(OutboxEvent.id)))
    assert remaining == 0
