"""Leased at-least-once outbox dispatch and periodic recovery."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from app.core.events import DomainEvent, EventPublisher
from app.db.session import Database
from app.repositories.outbox import OutboxRepository
from app.utilities.datetime import as_utc, utc_now

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DispatchResult:
    """One bounded dispatch pass outcome."""

    claimed: int
    published: int
    failed: int


class Dispatcher(Protocol):
    """Structural contract for the periodic worker."""

    async def dispatch_once(self) -> object:
        """Dispatch one bounded batch."""


class OutboxDispatcher:
    """Publish leased events and settle each result in a short transaction."""

    def __init__(
        self,
        database: Database,
        publisher: EventPublisher,
        *,
        batch_size: int,
        lease_seconds: float,
        retry_base_seconds: float,
        retry_max_seconds: float,
    ) -> None:
        if (
            batch_size < 1
            or lease_seconds <= 0
            or retry_base_seconds <= 0
            or retry_max_seconds < retry_base_seconds
        ):
            raise ValueError("Outbox dispatcher bounds are invalid")
        self.database = database
        self.publisher = publisher
        self.batch_size = batch_size
        self.lease_seconds = lease_seconds
        self.retry_base_seconds = retry_base_seconds
        self.retry_max_seconds = retry_max_seconds
        self._dispatch_lock = asyncio.Lock()

    async def dispatch_once(
        self,
        *,
        now: datetime | None = None,
    ) -> DispatchResult:
        """Claim, publish, and settle one serialized process-local batch."""
        async with self._dispatch_lock:
            return await self._dispatch_once(now=now or utc_now())

    async def _dispatch_once(self, *, now: datetime) -> DispatchResult:
        async with self.database.session() as session:
            async with session.begin():
                events = await OutboxRepository(session).claim_batch(
                    now,
                    limit=self.batch_size,
                    lease_seconds=self.lease_seconds,
                )

        published = 0
        failed = 0
        for event in events:
            domain_event = DomainEvent(
                id=event.id,
                room_code=event.room_code,
                type=event.event_type,
                payload=dict(event.payload),
                occurred_at=as_utc(event.occurred_at),
            )
            try:
                await self.publisher.publish_event(domain_event)
            except Exception as error:
                failed += 1
                retry_delay = min(
                    self.retry_max_seconds,
                    self.retry_base_seconds * (2 ** max(0, event.attempts - 1)),
                )
                async with self.database.session() as session:
                    async with session.begin():
                        await OutboxRepository(session).mark_failed(
                            event.id,
                            event.claim_token,
                            available_at=now + timedelta(seconds=retry_delay),
                            error=f"{type(error).__name__}: {error}",
                        )
                logger.warning(
                    "Outbox publication failed",
                    extra={"event": "outbox.publish_failed"},
                )
            else:
                async with self.database.session() as session:
                    async with session.begin():
                        settled = await OutboxRepository(session).mark_published(
                            event.id,
                            event.claim_token,
                            published_at=now,
                        )
                if settled:
                    published += 1
        return DispatchResult(len(events), published, failed)


class OutboxWorker:
    """Dispatch immediately on startup and periodically until stopped."""

    def __init__(self, dispatcher: Dispatcher, *, interval_seconds: float) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.dispatcher = dispatcher
        self.interval_seconds = interval_seconds
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.is_running:
            return
        self._stop.clear()
        await self.dispatcher.dispatch_once()
        self._task = asyncio.create_task(self._run(), name="tomanap-outbox-worker")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=self.interval_seconds,
                )
            except TimeoutError:
                try:
                    await self.dispatcher.dispatch_once()
                except Exception:
                    logger.exception("Outbox dispatch failed")
