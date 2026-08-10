"""API fixtures for authoritative round lifecycle tests."""

import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.base import Base
from app.db.session import Database
from app.main import create_app


async def _initialize_database(database_url: str) -> None:
    database = Database(database_url)
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await database.dispose()


@pytest.fixture
def gameplay_client(settings: Settings) -> Iterator[TestClient]:
    """Run gameplay APIs against a fresh isolated domain schema."""
    asyncio.run(_initialize_database(settings.database_url))
    database = Database(settings.database_url)
    with TestClient(create_app(settings, database=database)) as client:
        yield client
