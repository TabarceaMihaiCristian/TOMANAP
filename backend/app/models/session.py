"""Hashed anonymous browser-session persistence."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.player import Player


class AnonymousSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Opaque-token hashes that restore one anonymous player seat."""

    __tablename__ = "anonymous_sessions"
    __table_args__ = (
        CheckConstraint(
            "length(session_token_hash) = 64",
            name="session_token_hash_length",
        ),
        CheckConstraint(
            "length(reconnect_token_hash) = 64",
            name="reconnect_token_hash_length",
        ),
        CheckConstraint(
            "session_token_hash <> reconnect_token_hash",
            name="distinct_token_hashes",
        ),
    )

    player_id: Mapped[UUID] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    reconnect_token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    reconnect_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    player: Mapped[Player] = relationship(back_populates="sessions")
