"""Durable responses for atomically idempotent domain commands."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class IdempotencyRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One scoped command key and its committed JSON response."""

    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "operation",
            "key_hash",
            name="uq_idempotency_player_operation_key",
        ),
        CheckConstraint("length(key_hash) = 64", name="key_hash_length"),
        CheckConstraint("length(request_hash) = 64", name="request_hash_length"),
        CheckConstraint(
            "length(operation) BETWEEN 1 AND 120",
            name="operation_length",
        ),
        CheckConstraint(
            "completed_at IS NULL OR response_payload IS NOT NULL",
            name="completed_response_required",
        ),
    )

    player_id: Mapped[UUID] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation: Mapped[str] = mapped_column(String(120), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_payload: Mapped[dict[str, object] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
