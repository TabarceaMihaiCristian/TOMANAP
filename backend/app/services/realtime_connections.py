"""Process-local WebSocket capacity accounting."""

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID


class RealtimeCapacityError(Exception):
    """Raised when a room or player connection budget is exhausted."""


class RealtimeDrainingError(Exception):
    """Raised when shutdown has stopped accepting new connections."""


class RealtimeConnectionManager:
    """Bound connections per room and player with deterministic cleanup."""

    def __init__(
        self,
        *,
        max_connections_per_room: int,
        max_connections_per_player: int,
    ) -> None:
        if max_connections_per_room < 1 or max_connections_per_player < 1:
            raise ValueError("Realtime connection limits must be positive")
        self.max_connections_per_room = max_connections_per_room
        self.max_connections_per_player = max_connections_per_player
        self._rooms: dict[str, dict[UUID, int]] = defaultdict(dict)
        self._lock = asyncio.Lock()
        self._draining = False
        self._drain_started = asyncio.Event()
        self._empty = asyncio.Event()
        self._empty.set()

    @property
    def is_draining(self) -> bool:
        """Return whether new connections are being rejected."""
        return self._draining

    async def begin_draining(self) -> None:
        """Atomically reject new reservations and notify active sockets."""
        async with self._lock:
            self._draining = True
            self._drain_started.set()

    async def wait_for_drain(self) -> None:
        """Wait until graceful process shutdown begins."""
        await self._drain_started.wait()

    async def wait_until_empty(self, *, timeout_seconds: float) -> bool:
        """Wait a bounded time for all reserved connections to leave."""
        if self._empty.is_set():
            return True
        try:
            await asyncio.wait_for(self._empty.wait(), timeout=timeout_seconds)
        except TimeoutError:
            return False
        return True

    @asynccontextmanager
    async def register(self, room_code: str, player_id: UUID) -> AsyncIterator[None]:
        """Reserve capacity until the surrounding connection exits."""
        room = room_code.strip().upper()
        async with self._lock:
            if self._draining:
                raise RealtimeDrainingError()
            players = self._rooms[room]
            room_count = sum(players.values())
            player_count = players.get(player_id, 0)
            if (
                room_count >= self.max_connections_per_room
                or player_count >= self.max_connections_per_player
            ):
                if not players:
                    self._rooms.pop(room, None)
                raise RealtimeCapacityError()
            players[player_id] = player_count + 1
            self._empty.clear()
        try:
            yield
        finally:
            async with self._lock:
                players = self._rooms.get(room)
                if players is not None:
                    remaining = players.get(player_id, 0) - 1
                    if remaining > 0:
                        players[player_id] = remaining
                    else:
                        players.pop(player_id, None)
                    if not players:
                        self._rooms.pop(room, None)
                    if not self._rooms:
                        self._empty.set()

    def room_connection_count(self, room_code: str) -> int:
        """Return aggregate room usage for health and tests."""
        return sum(self._rooms.get(room_code.strip().upper(), {}).values())
