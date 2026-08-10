"""add transactional outbox

Revision ID: a71d84f6c920
Revises: 38314f08eb16
Create Date: 2026-07-12 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a71d84f6c920"
down_revision: str | Sequence[str] | None = "38314f08eb16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the durable at-least-once event table."""
    op.create_table(
        "outbox_events",
        sa.Column("room_code", sa.String(length=8), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claim_token", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
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
            "(claimed_at IS NULL AND claim_token IS NULL) OR "
            "(claimed_at IS NOT NULL AND claim_token IS NOT NULL)",
            name=op.f("ck_outbox_events_complete_claim"),
        ),
        sa.CheckConstraint(
            "length(event_type) BETWEEN 1 AND 80",
            name=op.f("ck_outbox_events_event_type_length"),
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name=op.f("ck_outbox_events_nonnegative_attempts"),
        ),
        sa.CheckConstraint(
            "published_at IS NULL OR (claimed_at IS NULL AND claim_token IS NULL)",
            name=op.f("ck_outbox_events_published_not_claimed"),
        ),
        sa.CheckConstraint(
            "length(room_code) BETWEEN 4 AND 8",
            name=op.f("ck_outbox_events_room_code_length"),
        ),
        sa.CheckConstraint(
            "room_code = upper(room_code)",
            name=op.f("ck_outbox_events_uppercase_room_code"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_events")),
    )
    op.create_index(
        op.f("ix_outbox_events_room_code"),
        "outbox_events",
        ["room_code"],
        unique=False,
    )
    op.create_index(
        "ix_outbox_events_pending",
        "outbox_events",
        ["published_at", "available_at", "claimed_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the transactional outbox."""
    op.drop_index("ix_outbox_events_pending", table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_room_code"), table_name="outbox_events")
    op.drop_table("outbox_events")
