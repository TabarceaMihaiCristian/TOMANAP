"""Persisted TOMANAP game and lobby configuration."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import (
    DEFAULT_ROUND_DURATION_SECONDS,
    MAX_ROUNDS,
    MIN_ROUNDS,
)
from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import GameStatus

if TYPE_CHECKING:
    from app.models.player import Player
    from app.models.round import Round


class Game(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A room-backed game whose state is controlled by server services."""

    __tablename__ = "games"
    __table_args__ = (
        CheckConstraint(
            f"round_count BETWEEN {MIN_ROUNDS} AND {MAX_ROUNDS}",
            name="round_count_bounds",
        ),
        CheckConstraint(
            "round_duration_seconds > 0",
            name="positive_round_duration",
        ),
        CheckConstraint(
            "length(room_code) BETWEEN 4 AND 8",
            name="room_code_length",
        ),
        CheckConstraint("room_code = upper(room_code)", name="uppercase_room_code"),
    )

    room_code: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[GameStatus] = mapped_column(
        Enum(
            GameStatus,
            name="game_status",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
        default=GameStatus.LOBBY,
        server_default=GameStatus.LOBBY.name,
        index=True,
    )
    round_count: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=5,
        server_default="5",
    )
    round_duration_seconds: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=DEFAULT_ROUND_DURATION_SECONDS,
        server_default=str(DEFAULT_ROUND_DURATION_SECONDS),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    players: Mapped[list[Player]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Player.seat_number",
    )
    rounds: Mapped[list[Round]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Round.sequence_number",
    )
