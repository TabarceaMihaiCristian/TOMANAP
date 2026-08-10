"""Tests for SQLAlchemy session and Alembic foundations."""

import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest
from sqlalchemy import text

from app.db.session import Database


@pytest.mark.asyncio
async def test_async_database_session_executes_and_closes(tmp_path: Path) -> None:
    database_path = (tmp_path / "session.db").as_posix()
    database = Database(f"sqlite+aiosqlite:///{database_path}")

    async with database.session() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1

    await database.dispose()


def test_migrations_upgrade_an_empty_database(tmp_path: Path) -> None:
    backend_root = Path(__file__).resolve().parents[2]
    database_path = tmp_path / "migration.db"
    environment = os.environ.copy()
    environment["TOMANAP_DATABASE_URL"] = (
        f"sqlite+aiosqlite:///{database_path.as_posix()}"
    )

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    with closing(sqlite3.connect(database_path)) as connection:
        version = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
    assert version is not None
