"""Per-player round answer snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.player import Player
    from app.models.round import Round


class Submission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Mutable draft that becomes immutable when finalized or expired."""

    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint(
            "round_id",
            "player_id",
            name="uq_submissions_round_player",
        ),
        ForeignKeyConstraint(
            ["game_id", "round_id"],
            ["rounds.game_id", "rounds.id"],
            name="fk_submissions_game_round",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["game_id", "player_id"],
            ["players.game_id", "players.id"],
            name="fk_submissions_game_player",
            ondelete="CASCADE",
        ),
        CheckConstraint("revision >= 1", name="positive_revision"),
        CheckConstraint(
            "NOT is_finalized OR finalized_at IS NOT NULL",
            name="finalized_timestamp_required",
        ),
    )

    game_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    round_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    player_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    answers: Mapped[dict[str, str]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    normalized_answers: Mapped[dict[str, str]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    is_finalized: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    __mapper_args__ = {"version_id_col": revision}

    round: Mapped[Round] = relationship(
        back_populates="submissions",
        foreign_keys=[round_id],
    )
    player: Mapped[Player] = relationship(
        back_populates="submissions",
        foreign_keys=[player_id],
    )
