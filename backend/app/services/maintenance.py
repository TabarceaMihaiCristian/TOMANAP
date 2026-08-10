"""Bounded retention cleanup for terminal and expired application data."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.session import Database
from app.models import (
    AnonymousSession,
    Game,
    IdempotencyRecord,
    OutboxEvent,
    RealtimeTicket,
)
from app.models.enums import GameStatus
from app.utilities.datetime import utc_now

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MaintenanceResult:
    """Deleted row counts from one bounded cleanup pass."""

    sessions: int
    realtime_tickets: int
    idempotency_records: int
    outbox_events: int
    games: int


class Maintainer(Protocol):
    """Structural contract used by the periodic worker."""

    async def run_once(self) -> object:
        """Run one cleanup pass."""


class MaintenanceService:
    """Delete only unusable credentials, settled events, and old games."""

    def __init__(self, database: Database, settings: Settings) -> None:
        self.database = database
        self.settings = settings
        self._lock = asyncio.Lock()

    async def run_once(self, *, now: datetime | None = None) -> MaintenanceResult:
        """Run one process-local serialized and transactionally bounded pass."""
        async with self._lock:
            return await self._run_once(now=now or utc_now())

    async def _run_once(self, *, now: datetime) -> MaintenanceResult:
        credential_cutoff = now - timedelta(
            hours=self.settings.credential_retention_hours
        )
        outbox_cutoff = now - timedelta(days=self.settings.outbox_retention_days)
        game_cutoff = now - timedelta(days=self.settings.completed_game_retention_days)
        async with self.database.session() as session:
            async with session.begin():
                sessions = await self._delete_batch(
                    session,
                    AnonymousSession,
                    or_(
                        AnonymousSession.reconnect_expires_at <= now,
                        and_(
                            AnonymousSession.revoked_at.is_not(None),
                            AnonymousSession.revoked_at <= credential_cutoff,
                        ),
                    ),
                    AnonymousSession.reconnect_expires_at,
                )
                realtime_tickets = await self._delete_batch(
                    session,
                    RealtimeTicket,
                    or_(
                        RealtimeTicket.expires_at <= now,
                        and_(
                            RealtimeTicket.consumed_at.is_not(None),
                            RealtimeTicket.consumed_at <= credential_cutoff,
                        ),
                    ),
                    RealtimeTicket.expires_at,
                )
                idempotency_records = await self._delete_batch(
                    session,
                    IdempotencyRecord,
                    IdempotencyRecord.expires_at <= now,
                    IdempotencyRecord.expires_at,
                )
                outbox_events = await self._delete_batch(
                    session,
                    OutboxEvent,
                    and_(
                        OutboxEvent.published_at.is_not(None),
                        OutboxEvent.published_at <= outbox_cutoff,
                    ),
                    OutboxEvent.published_at,
                )
                games = await self._delete_batch(
                    session,
                    Game,
                    and_(
                        Game.status == GameStatus.COMPLETED,
                        Game.completed_at.is_not(None),
                        Game.completed_at <= game_cutoff,
                    ),
                    Game.completed_at,
                )
        return MaintenanceResult(
            sessions=sessions,
            realtime_tickets=realtime_tickets,
            idempotency_records=idempotency_records,
            outbox_events=outbox_events,
            games=games,
        )

    async def _delete_batch(
        self,
        session: AsyncSession,
        model: type[Any],
        predicate: Any,
        order_column: Any,
    ) -> int:
        statement = (
            select(model.id)
            .where(predicate)
            .order_by(order_column, model.id)
            .limit(self.settings.maintenance_batch_size)
            .with_for_update(skip_locked=True)
        )
        record_ids = list((await session.scalars(statement)).all())
        if record_ids:
            await session.execute(
                delete(model)
                .where(model.id.in_(record_ids))
                .execution_options(synchronize_session=False)
            )
        return len(record_ids)


class MaintenanceWorker:
    """Run cleanup on startup and periodically until stopped."""

    def __init__(self, maintainer: Maintainer, *, interval_seconds: float) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.maintainer = maintainer
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
        await self.maintainer.run_once()
        self._task = asyncio.create_task(
            self._run(),
            name="tomanap-maintenance-worker",
        )

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
                    await self.maintainer.run_once()
                except Exception:
                    logger.exception("Retention cleanup failed")
