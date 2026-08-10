"""Anonymous player membership persisted within one game."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    false,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import MAX_PLAYERS
from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.game import Game
    from app.models.score import Score
    from app.models.session import AnonymousSession
    from app.models.submission import Submission


class Player(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An anonymous seat and its host/readiness state within a game."""

    __tablename__ = "players"
    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "normalized_display_name",
            name="uq_players_game_normalized_name",
        ),
        UniqueConstraint(
            "game_id",
            "seat_number",
            name="uq_players_game_seat",
        ),
        UniqueConstraint("game_id", "id", name="uq_players_game_id_id"),
        CheckConstraint(
            f"seat_number BETWEEN 1 AND {MAX_PLAYERS}",
            name="seat_number_bounds",
        ),
        CheckConstraint(
            "length(display_name) BETWEEN 1 AND 40",
            name="display_name_length",
        ),
        CheckConstraint(
            "length(normalized_display_name) BETWEEN 1 AND 40",
            name="normalized_display_name_length",
        ),
        CheckConstraint("cumulative_score >= 0", name="nonnegative_score"),
        CheckConstraint("NOT is_host OR is_active", name="host_is_active"),
        Index(
            "uq_players_one_host_per_game",
            "game_id",
            unique=True,
            sqlite_where=text("is_host = 1"),
            postgresql_where=text("is_host"),
        ),
        Index("ix_players_game_active", "game_id", "is_active"),
    )

    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(40), nullable=False)
    normalized_display_name: Mapped[str] = mapped_column(String(40), nullable=False)
    seat_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_host: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    is_ready: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    is_connected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    cumulative_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    game: Mapped[Game] = relationship(back_populates="players")
    sessions: Mapped[list[AnonymousSession]] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    submissions: Mapped[list[Submission]] = relationship(
        back_populates="player",
        foreign_keys="Submission.player_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    scores: Mapped[list[Score]] = relationship(
        back_populates="player",
        foreign_keys="Score.player_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
