"""Dependency-aware readiness checks with non-sensitive results."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from alembic.config import Config
from alembic.script import ScriptDirectory
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import Database


class Worker(Protocol):
    """Minimum worker state used by readiness checks."""

    @property
    def is_running(self) -> bool:
        """Return whether the periodic task is alive."""


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    """Stable readiness outcome safe to return to callers."""

    checks: dict[str, bool]

    @property
    def is_ready(self) -> bool:
        """Require every configured dependency and lifecycle check."""
        return all(self.checks.values())


class ReadinessService:
    """Check infrastructure without leaking connection or error details."""

    def __init__(
        self,
        database: Database,
        *,
        redis: Redis | None,
        workers: tuple[tuple[bool, Worker], ...],
    ) -> None:
        self.database = database
        self.redis = redis
        self.workers = workers
        self.expected_migration_heads = self._migration_heads()

    @staticmethod
    def _migration_heads() -> set[str]:
        backend_root = Path(__file__).resolve().parents[2]
        config = Config()
        config.set_main_option("script_location", str(backend_root / "alembic"))
        return set(ScriptDirectory.from_config(config).get_heads())

    async def check(self, *, accepting_traffic: bool) -> ReadinessReport:
        """Run bounded checks and collapse failures to booleans."""
        database_ok, migrations_ok = await self._check_database()
        redis_ok = await self._check_redis()
        workers_ok = all(
            not enabled or worker.is_running for enabled, worker in self.workers
        )
        return ReadinessReport(
            checks={
                "database": database_ok,
                "migrations": migrations_ok,
                "redis": redis_ok,
                "workers": workers_ok,
                "accepting_traffic": accepting_traffic,
            }
        )

    async def _check_database(self) -> tuple[bool, bool]:
        try:
            async with self.database.session() as session:
                await session.execute(text("SELECT 1"))
                try:
                    result = await session.execute(
                        text("SELECT version_num FROM alembic_version")
                    )
                except SQLAlchemyError:
                    return True, False
                current_heads = set(result.scalars().all())
        except SQLAlchemyError:
            return False, False
        return True, current_heads == self.expected_migration_heads

    async def _check_redis(self) -> bool:
        if self.redis is None:
            return True
        try:
            return bool(await self.redis.ping())
        except Exception:
            return False
