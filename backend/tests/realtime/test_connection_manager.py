"""Tests for bounded realtime connection accounting."""

from uuid import uuid4

import pytest

from app.services.realtime_connections import (
    RealtimeCapacityError,
    RealtimeConnectionManager,
    RealtimeDrainingError,
)


async def test_connection_manager_enforces_player_and_room_limits() -> None:
    manager = RealtimeConnectionManager(
        max_connections_per_room=2,
        max_connections_per_player=1,
    )
    first_player = uuid4()
    second_player = uuid4()
    third_player = uuid4()

    async with manager.register("ABC123", first_player):
        assert manager.room_connection_count("ABC123") == 1
        with pytest.raises(RealtimeCapacityError):
            async with manager.register("ABC123", first_player):
                pass
        async with manager.register("ABC123", second_player):
            assert manager.room_connection_count("ABC123") == 2
            with pytest.raises(RealtimeCapacityError):
                async with manager.register("ABC123", third_player):
                    pass

    assert manager.room_connection_count("ABC123") == 0


async def test_connection_manager_drains_existing_and_rejects_new_connections() -> None:
    manager = RealtimeConnectionManager(
        max_connections_per_room=2,
        max_connections_per_player=1,
    )

    async with manager.register("ABC123", uuid4()):
        await manager.begin_draining()

        await manager.wait_for_drain()
        assert manager.is_draining is True
        assert await manager.wait_until_empty(timeout_seconds=0.01) is False
        with pytest.raises(RealtimeDrainingError):
            async with manager.register("ABC123", uuid4()):
                pass

    assert await manager.wait_until_empty(timeout_seconds=0.01) is True
