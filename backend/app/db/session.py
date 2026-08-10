"""Async SQLAlchemy engine and session lifecycle."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, StaticPool


class Database:
    """Own an async engine and create short-lived request sessions."""

    def __init__(self, database_url: str, *, echo: bool = False) -> None:
        url = make_url(database_url)
        engine_options: dict[str, Any] = {
            "echo": echo,
            "pool_pre_ping": True,
        }
        if url.get_backend_name() == "sqlite":
            engine_options["poolclass"] = (
                StaticPool if url.database in {None, "", ":memory:"} else NullPool
            )
        self.engine: AsyncEngine = create_async_engine(
            database_url,
            **engine_options,
        )
        if self.engine.url.get_backend_name() == "sqlite":
            self._enable_sqlite_foreign_keys()
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

    def _enable_sqlite_foreign_keys(self) -> None:
        """Enable SQLite's opt-in foreign-key and cascade enforcement."""

        @event.listens_for(self.engine.sync_engine, "connect")
        def set_sqlite_pragma(
            dbapi_connection: Any,
            _connection_record: Any,
        ) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a session and deterministically return its connection."""
        async with self.session_factory() as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise
            finally:
                if session.in_transaction():
                    await session.rollback()

    async def dispose(self) -> None:
        """Release all pooled database connections."""
        await self.engine.dispose()
