"""Tests for the initial TOMANAP domain migration."""

import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

DOMAIN_TABLES = {
    "games",
    "players",
    "anonymous_sessions",
    "rounds",
    "submissions",
    "scores",
    "outbox_events",
    "realtime_tickets",
    "idempotency_records",
}


def _run_alembic(backend_root: Path, environment: dict[str, str], *args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=backend_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _table_names(database_path: Path) -> set[str]:
    with closing(sqlite3.connect(database_path)) as connection:
        return {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }


def test_migration_creates_and_removes_the_complete_domain_schema(
    tmp_path: Path,
) -> None:
    backend_root = Path(__file__).resolve().parents[2]
    database_path = tmp_path / "migration.db"
    environment = os.environ.copy()
    environment["TOMANAP_DATABASE_URL"] = (
        f"sqlite+aiosqlite:///{database_path.as_posix()}"
    )

    _run_alembic(backend_root, environment, "upgrade", "head")
    tables = _table_names(database_path)
    assert DOMAIN_TABLES <= tables
    assert "invitations" not in tables
    with closing(sqlite3.connect(database_path)) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO games (id, room_code) VALUES (?, ?)",
                ("0" * 32, "lower1"),
            )

    _run_alembic(backend_root, environment, "downgrade", "base")
    assert not (DOMAIN_TABLES & _table_names(database_path))
