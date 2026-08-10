"""Tests for bounded entry-point abuse protection."""

import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.rate_limiting import SlidingWindowRateLimiter
from app.db.base import Base
from app.db.session import Database
from app.main import create_app


async def _initialize_database(database_url: str) -> None:
    database = Database(database_url)
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await database.dispose()


@pytest.fixture
def limited_client(settings: Settings) -> Iterator[TestClient]:
    limited_settings = settings.model_copy(
        update={
            "entry_rate_limit_requests": 2,
            "entry_rate_limit_window_seconds": 60,
        }
    )
    asyncio.run(_initialize_database(limited_settings.database_url))
    database = Database(limited_settings.database_url)
    with TestClient(create_app(limited_settings, database=database)) as client:
        yield client


async def test_sliding_window_is_bounded_and_recovers_after_window() -> None:
    now = 100.0
    limiter = SlidingWindowRateLimiter(
        requests=2,
        window_seconds=10,
        max_keys=2,
        clock=lambda: now,
    )

    assert (await limiter.check("first")).allowed is True
    assert (await limiter.check("first")).allowed is True
    denied = await limiter.check("first")
    assert denied.allowed is False
    assert denied.retry_after_seconds == 10

    await limiter.check("second")
    await limiter.check("third")
    assert limiter.tracked_key_count == 2

    now = 111.0
    assert (await limiter.check("first")).allowed is True


def test_room_creation_rate_limit_returns_retry_contract(
    limited_client: TestClient,
) -> None:
    request = {
        "display_name": "Mihai",
        "round_count": 3,
        "round_duration_seconds": 60,
    }
    assert limited_client.post("/games", json=request).status_code == 201
    request["display_name"] = "Ana"
    assert limited_client.post("/games", json=request).status_code == 201
    request["display_name"] = "Radu"
    denied = limited_client.post("/games", json=request)

    assert denied.status_code == 429
    assert denied.headers["Retry-After"] == "60"
    assert denied.json() == {
        "error": {
            "code": "rate_limit_exceeded",
            "message": "Too many requests",
        }
    }


def test_sql_metacharacters_are_data_and_cannot_modify_schema(
    limited_client: TestClient,
) -> None:
    malicious_name = "Robert'); DROP TABLE games;--"
    first = limited_client.post(
        "/games",
        json={
            "display_name": malicious_name,
            "round_count": 1,
            "round_duration_seconds": 60,
        },
    )
    second = limited_client.post(
        "/games",
        json={
            "display_name": "Still here",
            "round_count": 1,
            "round_duration_seconds": 60,
        },
    )

    assert first.status_code == 201
    assert first.json()["game"]["players"][0]["display_name"] == malicious_name
    assert second.status_code == 201
