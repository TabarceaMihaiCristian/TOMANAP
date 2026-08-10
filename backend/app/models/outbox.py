"""Durable at-least-once domain event outbox."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, DateTime, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class OutboxEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One committed event awaiting publication to realtime consumers."""

    __tablename__ = "outbox_events"
    __table_args__ = (
        CheckConstraint(
            "length(room_code) BETWEEN 4 AND 8",
            name="room_code_length",
        ),
        CheckConstraint("room_code = upper(room_code)", name="uppercase_room_code"),
        CheckConstraint(
            "length(event_type) BETWEEN 1 AND 80",
            name="event_type_length",
        ),
        CheckConstraint("attempts >= 0", name="nonnegative_attempts"),
        CheckConstraint(
            "(claimed_at IS NULL AND claim_token IS NULL) OR "
            "(claimed_at IS NOT NULL AND claim_token IS NOT NULL)",
            name="complete_claim",
        ),
        CheckConstraint(
            "published_at IS NULL OR (claimed_at IS NULL AND claim_token IS NULL)",
            name="published_not_claimed",
        ),
        Index(
            "ix_outbox_events_pending",
            "published_at",
            "available_at",
            "claimed_at",
        ),
    )

    room_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    claim_token: Mapped[UUID | None] = mapped_column(nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
