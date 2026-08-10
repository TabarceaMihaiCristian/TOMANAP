"""add realtime tickets

Revision ID: c82f9241d630
Revises: a71d84f6c920
Create Date: 2026-07-12 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c82f9241d630"
down_revision: str | Sequence[str] | None = "a71d84f6c920"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create hashed, short-lived WebSocket handshake tickets."""
    op.create_table(
        "realtime_tickets",
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("ticket_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(ticket_hash) = 64",
            name=op.f("ck_realtime_tickets_ticket_hash_length"),
        ),
        sa.ForeignKeyConstraint(
            ["game_id", "player_id"],
            ["players.game_id", "players.id"],
            name="fk_realtime_tickets_game_player",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_realtime_tickets")),
    )
    op.create_index(
        op.f("ix_realtime_tickets_consumed_at"),
        "realtime_tickets",
        ["consumed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_realtime_tickets_expires_at"),
        "realtime_tickets",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_realtime_tickets_game_id"),
        "realtime_tickets",
        ["game_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_realtime_tickets_player_id"),
        "realtime_tickets",
        ["player_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_realtime_tickets_ticket_hash"),
        "realtime_tickets",
        ["ticket_hash"],
        unique=True,
    )


def downgrade() -> None:
    """Remove WebSocket handshake tickets."""
    op.drop_index(
        op.f("ix_realtime_tickets_ticket_hash"),
        table_name="realtime_tickets",
    )
    op.drop_index(
        op.f("ix_realtime_tickets_player_id"),
        table_name="realtime_tickets",
    )
    op.drop_index(
        op.f("ix_realtime_tickets_game_id"),
        table_name="realtime_tickets",
    )
    op.drop_index(
        op.f("ix_realtime_tickets_expires_at"),
        table_name="realtime_tickets",
    )
    op.drop_index(
        op.f("ix_realtime_tickets_consumed_at"),
        table_name="realtime_tickets",
    )
    op.drop_table("realtime_tickets")
