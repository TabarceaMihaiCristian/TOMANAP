"""Persisted authoritative round lifecycle."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import MAX_ROUNDS, MIN_ROUNDS
from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RoundStatus

if TYPE_CHECKING:
    from app.models.game import Game
    from app.models.score import Score
    from app.models.submission import Submission


class Round(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One selected letter, deadline, and finalization record in a game."""

    __tablename__ = "rounds"
    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "sequence_number",
            name="uq_rounds_game_sequence",
        ),
        UniqueConstraint("game_id", "letter", name="uq_rounds_game_letter"),
        UniqueConstraint("game_id", "id", name="uq_rounds_game_id_id"),
        CheckConstraint(
            f"sequence_number BETWEEN {MIN_ROUNDS} AND {MAX_ROUNDS}",
            name="sequence_number_bounds",
        ),
        CheckConstraint("length(letter) = 1", name="single_letter"),
        CheckConstraint("letter = upper(letter)", name="uppercase_letter"),
        CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at",
            name="valid_deadline_window",
        ),
        CheckConstraint(
            "NOT is_current OR status <> 'COMPLETED'",
            name="current_round_not_completed",
        ),
        Index(
            "uq_rounds_one_current_per_game",
            "game_id",
            unique=True,
            sqlite_where=text("is_current = 1"),
            postgresql_where=text("is_current"),
        ),
        Index("ix_rounds_game_status", "game_id", "status"),
    )

    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    letter: Mapped[str] = mapped_column(String(1), nullable=False)
    status: Mapped[RoundStatus] = mapped_column(
        Enum(
            RoundStatus,
            name="round_status",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
        default=RoundStatus.PENDING,
        server_default=RoundStatus.PENDING.name,
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    scored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    game: Mapped[Game] = relationship(back_populates="rounds")
    submissions: Mapped[list[Submission]] = relationship(
        back_populates="round",
        foreign_keys="Submission.round_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    scores: Mapped[list[Score]] = relationship(
        back_populates="round",
        foreign_keys="Score.round_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
