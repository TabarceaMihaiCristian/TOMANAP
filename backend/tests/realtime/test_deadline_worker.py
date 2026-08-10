"""Tests for deadline recovery and the cancellable periodic worker."""

import asyncio
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.services.timers import DeadlineWorker

SESSION_HEADER = "X-TOMANAP-Session"


def _start_game(client: TestClient) -> tuple[dict[str, Any], str]:
    host_response = client.post(
        "/games",
        json={
            "display_name": "Mihai",
            "round_count": 1,
            "round_duration_seconds": 60,
        },
    )
    host = host_response.json()
    room_code = host["game"]["room_code"]
    guest_response = client.post(
        f"/games/{room_code}/join",
        json={"display_name": "Ana"},
    )
    guest = guest_response.json()
    assert (
        client.post(
            f"/games/{room_code}/ready",
            headers={SESSION_HEADER: guest["session_token"]},
            json={"is_ready": True},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/games/{room_code}/start",
            headers={SESSION_HEADER: host["session_token"]},
        ).status_code
        == 200
    )
    current = client.get(
        f"/games/{room_code}/rounds/current",
        headers={SESSION_HEADER: host["session_token"]},
    ).json()
    return host, current["round"]["id"]


def test_sweeper_recovers_expired_round_exactly_once(
    publication_client: tuple[TestClient, Any],
    settings: Settings,
) -> None:
    client, broker = publication_client
    host, round_id = _start_game(client)
    database_path = Path(settings.database_url.removeprefix("sqlite+aiosqlite:///"))
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(
            "UPDATE rounds SET starts_at = ?, ends_at = ?",
            (
                "1999-12-31 23:59:00.000000",
                "2000-01-01 00:00:00.000000",
            ),
        )
        connection.commit()

    sweeper = client.app.state.deadline_sweeper
    assert client.portal is not None
    assert client.portal.call(sweeper.sweep_once) == 1
    assert client.portal.call(sweeper.sweep_once) == 0

    closure_events = [event for event in broker.events if event.type == "round.closed"]
    assert len(closure_events) == 1
    assert closure_events[0].room_code == host["game"]["room_code"]
    assert closure_events[0].payload == {
        "round_id": round_id,
        "reason": "deadline_reached",
    }


def test_overlapping_sweeps_preserve_exactly_once_scoring(
    publication_client: tuple[TestClient, Any],
    settings: Settings,
) -> None:
    client, broker = publication_client
    _host, _round_id = _start_game(client)
    database_path = Path(settings.database_url.removeprefix("sqlite+aiosqlite:///"))
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(
            "UPDATE rounds SET starts_at = ?, ends_at = ?",
            (
                "1999-12-31 23:59:00.000000",
                "2000-01-01 00:00:00.000000",
            ),
        )
        connection.commit()

    sweeper = client.app.state.deadline_sweeper

    async def race() -> list[int]:
        return list(await asyncio.gather(sweeper.sweep_once(), sweeper.sweep_once()))

    assert client.portal is not None
    assert sorted(client.portal.call(race)) == [0, 1]
    with closing(sqlite3.connect(database_path)) as connection:
        score_count = connection.execute("SELECT count(*) FROM scores").fetchone()[0]
        scored_rounds = connection.execute(
            "SELECT count(*) FROM rounds WHERE scored_at IS NOT NULL"
        ).fetchone()[0]

    assert score_count == 14
    assert scored_rounds == 1
    assert sum(event.type == "round.closed" for event in broker.events) == 1


async def test_deadline_worker_repeats_and_stops_cleanly() -> None:
    calls = 0
    repeated = asyncio.Event()

    class FakeSweeper:
        async def sweep_once(self) -> int:
            nonlocal calls
            calls += 1
            if calls >= 2:
                repeated.set()
            return 0

    worker = DeadlineWorker(FakeSweeper(), interval_seconds=0.01)
    await worker.start()
    await asyncio.wait_for(repeated.wait(), timeout=0.2)
    await worker.stop()

    calls_after_stop = calls
    await asyncio.sleep(0.03)
    assert calls == calls_after_stop
    assert worker.is_running is False
