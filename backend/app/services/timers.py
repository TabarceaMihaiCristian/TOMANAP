"""Deadline recovery and periodic authoritative round closure."""

import asyncio
import logging
from typing import Protocol

from app.core.config import Settings
from app.db.session import Database
from app.repositories.rounds import RoundRepository
from app.services.outbox import OutboxDispatcher
from app.services.rounds import RoundService
from app.utilities.datetime import utc_now

logger = logging.getLogger(__name__)


class Sweeper(Protocol):
    """Structural contract used by the periodic worker."""

    async def sweep_once(self) -> int:
        """Close one bounded batch and return its size."""


class DeadlineSweeper:
    """Find expired rounds and close each in its own short transaction."""

    def __init__(
        self,
        database: Database,
        settings: Settings,
        dispatcher: OutboxDispatcher,
    ) -> None:
        self.database = database
        self.settings = settings
        self.dispatcher = dispatcher
        self._sweep_lock = asyncio.Lock()

    async def sweep_once(self) -> int:
        """Recover a bounded batch, rechecking state under row locks."""
        async with self._sweep_lock:
            return await self._sweep_once()

    async def _sweep_once(self) -> int:
        """Run one serialized process-local recovery pass."""
        checked_at = utc_now()
        async with self.database.session() as session:
            async with session.begin():
                due_ids = await RoundRepository(session).list_due_ids(
                    checked_at,
                    limit=self.settings.deadline_sweep_batch_size,
                )

        closures = []
        for round_id in due_ids:
            async with self.database.session() as session:
                closure = await RoundService(
                    session,
                    self.settings,
                ).close_due_round(round_id, now=checked_at)
            if closure is not None:
                closures.append(closure)

        if closures:
            await self.dispatcher.dispatch_once(now=checked_at)
        return len(closures)


class DeadlineWorker:
    """Run startup recovery and periodic sweeps until clean cancellation."""

    def __init__(self, sweeper: Sweeper, *, interval_seconds: float) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.sweeper = sweeper
        self.interval_seconds = interval_seconds
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Recover missed deadlines before accepting periodic operation."""
        if self.is_running:
            return
        self._stop.clear()
        await self.sweeper.sweep_once()
        self._task = asyncio.create_task(
            self._run(),
            name="tomanap-deadline-worker",
        )

    async def stop(self) -> None:
        """Stop promptly and wait for the worker task to finish."""
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
                    await self.sweeper.sweep_once()
                except Exception:
                    logger.exception("Deadline sweep failed")
