"""Persistence tests for leased transactional outbox events."""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OutboxEvent
from app.repositories.outbox import OutboxRepository
from tests.persistence.helpers import NOW


async def test_outbox_claims_only_available_unpublished_events(
    session: AsyncSession,
) -> None:
    repository = OutboxRepository(session)
    available = await repository.add(
        OutboxEvent(
            room_code="ABC123",
            event_type="round.closed",
            payload={"round_id": "round-1"},
            occurred_at=NOW,
            available_at=NOW,
        )
    )
    await repository.add(
        OutboxEvent(
            room_code="ABC123",
            event_type="round.started",
            payload={},
            occurred_at=NOW,
            available_at=NOW + timedelta(minutes=1),
        )
    )
    published = await repository.add(
        OutboxEvent(
            room_code="ABC123",
            event_type="game.completed",
            payload={},
            occurred_at=NOW,
            available_at=NOW,
            published_at=NOW,
        )
    )
    await session.commit()

    async with session.begin():
        claimed = await repository.claim_batch(
            NOW,
            limit=10,
            lease_seconds=30,
        )

    assert [event.id for event in claimed] == [available.id]
    assert claimed[0].claim_token is not None
    assert claimed[0].claimed_at == NOW
    assert claimed[0].attempts == 1
    assert published.published_at == NOW


async def test_outbox_reclaims_expired_lease_and_requires_matching_claim(
    session: AsyncSession,
) -> None:
    repository = OutboxRepository(session)
    event = await repository.add(
        OutboxEvent(
            room_code="ABC123",
            event_type="lobby.updated",
            payload={},
            occurred_at=NOW,
            available_at=NOW,
        )
    )
    await session.commit()

    async with session.begin():
        first_claim = (await repository.claim_batch(NOW, limit=1, lease_seconds=5))[0]
        first_token = first_claim.claim_token
    async with session.begin():
        assert (
            await repository.claim_batch(
                NOW + timedelta(seconds=4),
                limit=1,
                lease_seconds=5,
            )
            == []
        )
    async with session.begin():
        reclaimed = (
            await repository.claim_batch(
                NOW + timedelta(seconds=6),
                limit=1,
                lease_seconds=5,
            )
        )[0]

    assert reclaimed.id == event.id
    assert reclaimed.claim_token != first_token
    assert reclaimed.attempts == 2
    async with session.begin():
        assert (
            await repository.mark_published(
                event.id,
                first_token,
                published_at=NOW + timedelta(seconds=7),
            )
            is False
        )
        assert (
            await repository.mark_published(
                event.id,
                reclaimed.claim_token,
                published_at=NOW + timedelta(seconds=7),
            )
            is True
        )


async def test_outbox_failure_releases_claim_and_schedules_retry(
    session: AsyncSession,
) -> None:
    repository = OutboxRepository(session)
    event = await repository.add(
        OutboxEvent(
            room_code="ABC123",
            event_type="submission.finalized",
            payload={"player_id": "player-1"},
            occurred_at=NOW,
            available_at=NOW,
        )
    )
    await session.commit()
    async with session.begin():
        claimed = (await repository.claim_batch(NOW, limit=1, lease_seconds=5))[0]
    retry_at = NOW + timedelta(seconds=10)

    async with session.begin():
        updated = await repository.mark_failed(
            event.id,
            claimed.claim_token,
            available_at=retry_at,
            error="broker unavailable" * 100,
        )

    assert updated is True
    assert event.claim_token is None
    assert event.claimed_at is None
    assert event.available_at == retry_at
    assert event.published_at is None
    assert event.last_error is not None
    assert len(event.last_error) <= 500
