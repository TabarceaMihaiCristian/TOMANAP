"""Auditable per-category score records."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKeyConstraint,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import Category
from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.player import Player
    from app.models.round import Round


class Score(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One player's scored answer for one category in one round."""

    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint(
            "round_id",
            "player_id",
            "category",
            name="uq_scores_round_player_category",
        ),
        ForeignKeyConstraint(
            ["game_id", "round_id"],
            ["rounds.game_id", "rounds.id"],
            name="fk_scores_game_round",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["game_id", "player_id"],
            ["players.game_id", "players.id"],
            name="fk_scores_game_player",
            ondelete="CASCADE",
        ),
        CheckConstraint("points IN (0, 5, 10)", name="valid_points"),
    )

    game_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    round_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    player_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    category: Mapped[Category] = mapped_column(
        Enum(
            Category,
            name="score_category",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
    )
    points: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    original_answer: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="",
        server_default="",
    )
    normalized_answer: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="",
        server_default="",
    )
    validation_code: Mapped[str | None] = mapped_column(String(32), nullable=True)

    round: Mapped[Round] = relationship(
        back_populates="scores",
        foreign_keys=[round_id],
    )
    player: Mapped[Player] = relationship(
        back_populates="scores",
        foreign_keys=[player_id],
    )
