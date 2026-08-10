"""Fixtures for opt-in real infrastructure contract tests."""

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.db.session import Database


@pytest.fixture
def postgres_url() -> str:
    value = os.environ.get("TOMANAP_TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TOMANAP_TEST_DATABASE_URL is not configured")
    return value


@pytest_asyncio.fixture
async def postgres_database(postgres_url: str) -> AsyncIterator[Database]:
    """Provide a migrated PostgreSQL database with domain tables emptied."""
    database = Database(postgres_url)
    truncate = text(
        "TRUNCATE TABLE games, players, anonymous_sessions, rounds, "
        "submissions, scores, outbox_events, realtime_tickets, "
        "idempotency_records RESTART IDENTITY CASCADE"
    )
    try:
        async with database.engine.begin() as connection:
            await connection.execute(truncate)
        yield database
    finally:
        async with database.engine.begin() as connection:
            await connection.execute(truncate)
        await database.dispose()
