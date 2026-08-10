"""Tests for bounded, room-scoped realtime event distribution."""

import asyncio

from app.services.realtime import RealtimeBroker


async def test_broker_isolates_rooms_and_removes_subscribers() -> None:
    broker = RealtimeBroker(max_queue_size=4)

    async with broker.subscribe("ABC123") as first_queue:
        async with broker.subscribe("XYZ789") as second_queue:
            event = await broker.publish(
                "ABC123",
                "lobby.updated",
                {"players": 2},
            )

            assert await asyncio.wait_for(first_queue.get(), timeout=0.1) == event
            assert second_queue.empty()
            assert broker.subscriber_count("ABC123") == 1

    assert broker.subscriber_count("ABC123") == 0
    assert broker.subscriber_count("XYZ789") == 0


async def test_broker_drops_oldest_event_for_a_slow_subscriber() -> None:
    broker = RealtimeBroker(max_queue_size=2)

    async with broker.subscribe("ABC123") as queue:
        await broker.publish("ABC123", "event.one", {})
        second = await broker.publish("ABC123", "event.two", {})
        third = await broker.publish("ABC123", "event.three", {})

        assert await queue.get() == second
        assert await queue.get() == third
        assert queue.empty()
