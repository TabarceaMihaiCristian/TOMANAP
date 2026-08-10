"""Persistence-layer fixtures backed by an isolated SQLite database."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.db.session import Database


@pytest_asyncio.fixture
async def database(tmp_path: Path) -> AsyncIterator[Database]:
    """Create all registered models in an isolated database."""
    database_path = (tmp_path / "persistence.db").as_posix()
    database = Database(f"sqlite+aiosqlite:///{database_path}")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield database
    finally:
        await database.dispose()


@pytest_asyncio.fixture
async def session(database: Database) -> AsyncIterator[AsyncSession]:
    """Provide a session whose uncommitted work is discarded after a test."""
    async with database.session() as session:
        yield session
        await session.rollback()
