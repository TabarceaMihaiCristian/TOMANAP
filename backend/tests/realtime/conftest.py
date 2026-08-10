"""Isolated application fixture for realtime API tests."""

import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.base import Base
from app.db.session import Database
from app.main import create_app
from app.services.realtime import RealtimeBroker, RealtimeEvent


class RecordingBroker(RealtimeBroker):
    """Record events while retaining production broker behavior."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[RealtimeEvent] = []

    async def publish(self, *args, **kwargs) -> RealtimeEvent:  # type: ignore[no-untyped-def]
        event = await super().publish(*args, **kwargs)
        self.events.append(event)
        return event


async def _initialize_database(database_url: str) -> None:
    database = Database(database_url)
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await database.dispose()


@pytest.fixture
def realtime_client(settings: Settings) -> Iterator[TestClient]:
    """Run realtime APIs against a fresh isolated domain schema."""
    asyncio.run(_initialize_database(settings.database_url))
    database = Database(settings.database_url)
    with TestClient(create_app(settings, database=database)) as client:
        yield client


@pytest.fixture
def publication_client(
    settings: Settings,
) -> Iterator[tuple[TestClient, RecordingBroker]]:
    """Expose recorded post-commit events from an isolated application."""
    asyncio.run(_initialize_database(settings.database_url))
    database = Database(settings.database_url)
    broker = RecordingBroker()
    with TestClient(
        create_app(settings, database=database, realtime_broker=broker)
    ) as client:
        yield client, broker


@pytest_asyncio.fixture
async def outbox_database(tmp_path: Path) -> AsyncIterator[Database]:
    """Provide an isolated async database for dispatcher tests."""
    database_path = (tmp_path / "outbox.db").as_posix()
    database = Database(f"sqlite+aiosqlite:///{database_path}")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield database
    finally:
        await database.dispose()
