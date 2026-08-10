"""Transaction-bound idempotency orchestration."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from pydantic_core import to_jsonable_python
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import IdempotencyConflictError
from app.core.security import hash_token
from app.models import IdempotencyRecord
from app.repositories.idempotency import IdempotencyRepository
from app.utilities.datetime import as_utc


@dataclass(frozen=True, slots=True)
class IdempotencyAttempt:
    """New record to complete or a previously committed response."""

    record: IdempotencyRecord
    replay_payload: dict[str, object] | None


class IdempotencyService:
    """Stage a key in the same transaction as its domain mutation."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.records = IdempotencyRepository(session)

    async def begin(
        self,
        player_id: UUID,
        operation: str,
        key: str | None,
        *,
        request_fingerprint: str,
        now: datetime,
    ) -> IdempotencyAttempt | None:
        if key is None:
            return None
        key_hash = hash_token(key)
        request_hash = hash_token(request_fingerprint)
        existing = await self.records.lock(player_id, operation, key_hash)
        if existing is not None and as_utc(existing.expires_at) <= now:
            await self.records.delete(existing)
            existing = None
        if existing is not None:
            if existing.request_hash != request_hash:
                raise IdempotencyConflictError(
                    "Idempotency key was already used for a different request"
                )
            if existing.completed_at is None or existing.response_payload is None:
                raise IdempotencyConflictError("Idempotent command is still pending")
            return IdempotencyAttempt(existing, dict(existing.response_payload))

        record = await self.records.add(
            IdempotencyRecord(
                player_id=player_id,
                operation=operation,
                key_hash=key_hash,
                request_hash=request_hash,
                expires_at=now + timedelta(hours=self.settings.idempotency_ttl_hours),
            )
        )
        return IdempotencyAttempt(record, None)

    async def complete(
        self,
        attempt: IdempotencyAttempt | None,
        response_payload: object,
        *,
        completed_at: datetime,
    ) -> None:
        if attempt is None:
            return
        payload = to_jsonable_python(response_payload)
        if not isinstance(payload, dict):
            raise TypeError("Idempotency response must serialize to an object")
        attempt.record.response_payload = payload
        attempt.record.completed_at = completed_at
        await self.session.flush()
