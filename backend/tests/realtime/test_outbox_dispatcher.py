"""Tests for at-least-once outbox publication and retry."""

import asyncio
from datetime import timedelta

from app.core.events import DomainEvent
from app.db.session import Database
from app.models import OutboxEvent
from app.repositories.outbox import OutboxRepository
from app.services.outbox import OutboxDispatcher, OutboxWorker
from app.utilities.datetime import as_utc
from tests.persistence.helpers import NOW


class RecordingPublisher:
    """Deterministic publisher that can fail a configured number of calls."""

    def __init__(self, *, failures: int = 0) -> None:
        self.failures = failures
        self.events: list[DomainEvent] = []

    async def publish_event(self, event: DomainEvent) -> None:
        if self.failures:
            self.failures -= 1
            raise RuntimeError("broker unavailable")
        self.events.append(event)


async def _stage_event(database: Database) -> OutboxEvent:
    async with database.session() as session:
        async with session.begin():
            return await OutboxRepository(session).add(
                OutboxEvent(
                    room_code="ABC123",
                    event_type="round.closed",
                    payload={"round_id": "round-1"},
                    occurred_at=NOW,
                    available_at=NOW,
                )
            )


async def _reload(database: Database, event_id) -> OutboxEvent:
    async with database.session() as session:
        async with session.begin():
            event = await session.get(OutboxEvent, event_id)
            assert event is not None
            return event


async def test_dispatcher_publishes_stable_event_id_and_settles(
    outbox_database: Database,
) -> None:
    database = outbox_database
    persisted = await _stage_event(database)
    publisher = RecordingPublisher()
    dispatcher = OutboxDispatcher(
        database,
        publisher,
        batch_size=10,
        lease_seconds=30,
        retry_base_seconds=5,
        retry_max_seconds=60,
    )

    result = await dispatcher.dispatch_once(now=NOW)

    assert result.claimed == 1
    assert result.published == 1
    assert result.failed == 0
    assert publisher.events == [
        DomainEvent(
            id=persisted.id,
            room_code="ABC123",
            type="round.closed",
            payload={"round_id": "round-1"},
            occurred_at=NOW,
        )
    ]
    reloaded = await _reload(database, persisted.id)
    assert as_utc(reloaded.published_at) == NOW
    assert reloaded.claim_token is None


async def test_dispatcher_retries_failure_after_exponential_delay(
    outbox_database: Database,
) -> None:
    database = outbox_database
    persisted = await _stage_event(database)
    publisher = RecordingPublisher(failures=1)
    dispatcher = OutboxDispatcher(
        database,
        publisher,
        batch_size=10,
        lease_seconds=30,
        retry_base_seconds=5,
        retry_max_seconds=60,
    )

    failed = await dispatcher.dispatch_once(now=NOW)
    too_early = await dispatcher.dispatch_once(now=NOW + timedelta(seconds=4))
    recovered = await dispatcher.dispatch_once(now=NOW + timedelta(seconds=5))

    assert (failed.claimed, failed.published, failed.failed) == (1, 0, 1)
    assert too_early.claimed == 0
    assert (recovered.claimed, recovered.published, recovered.failed) == (1, 1, 0)
    assert publisher.events[0].id == persisted.id
    reloaded = await _reload(database, persisted.id)
    assert reloaded.attempts == 2
    assert as_utc(reloaded.published_at) == NOW + timedelta(seconds=5)


async def test_outbox_worker_repeats_and_stops_cleanly() -> None:
    calls = 0
    repeated = asyncio.Event()

    class FakeDispatcher:
        async def dispatch_once(self):  # type: ignore[no-untyped-def]
            nonlocal calls
            calls += 1
            if calls >= 2:
                repeated.set()

    worker = OutboxWorker(FakeDispatcher(), interval_seconds=0.01)
    await worker.start()
    await asyncio.wait_for(repeated.wait(), timeout=0.2)
    await worker.stop()

    calls_after_stop = calls
    await asyncio.sleep(0.03)
    assert calls == calls_after_stop
    assert worker.is_running is False
