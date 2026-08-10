"""Shared test fixtures for the TOMANAP backend."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Environment, Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Return isolated settings suitable for API and database tests."""
    database_path = (tmp_path / "test.db").as_posix()
    return Settings(
        _env_file=None,
        environment=Environment.TEST,
        database_url=f"sqlite+aiosqlite:///{database_path}",
        cors_origins=("https://game.example.test",),
        allowed_hosts=("testserver",),
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """Run the application lifespan around a test client."""
    from app.main import create_app

    with TestClient(create_app(settings)) as test_client:
        yield test_client
