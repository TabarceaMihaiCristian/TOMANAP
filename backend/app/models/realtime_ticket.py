"""Short-lived, single-use credentials for WebSocket handshakes."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class RealtimeTicket(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Hashed room-bound ticket that can be consumed exactly once."""

    __tablename__ = "realtime_tickets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["game_id", "player_id"],
            ["players.game_id", "players.id"],
            name="fk_realtime_tickets_game_player",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "length(ticket_hash) = 64",
            name="ticket_hash_length",
        ),
    )

    game_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    player_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    ticket_hash: Mapped[str] = mapped_column(
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
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
