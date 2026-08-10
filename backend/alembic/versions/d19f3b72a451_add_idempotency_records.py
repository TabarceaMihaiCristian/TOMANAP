"""add idempotency records

Revision ID: d19f3b72a451
Revises: c82f9241d630
Create Date: 2026-07-12 23:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d19f3b72a451"
down_revision: str | Sequence[str] | None = "c82f9241d630"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create atomically committed command responses."""
    op.create_table(
        "idempotency_records",
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=120), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
            "completed_at IS NULL OR response_payload IS NOT NULL",
            name=op.f("ck_idempotency_records_completed_response_required"),
        ),
        sa.CheckConstraint(
            "length(key_hash) = 64",
            name=op.f("ck_idempotency_records_key_hash_length"),
        ),
        sa.CheckConstraint(
            "length(operation) BETWEEN 1 AND 120",
            name=op.f("ck_idempotency_records_operation_length"),
        ),
        sa.CheckConstraint(
            "length(request_hash) = 64",
            name=op.f("ck_idempotency_records_request_hash_length"),
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
            name=op.f("fk_idempotency_records_player_id_players"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_idempotency_records")),
        sa.UniqueConstraint(
            "player_id",
            "operation",
            "key_hash",
            name="uq_idempotency_player_operation_key",
        ),
    )
    op.create_index(
        op.f("ix_idempotency_records_expires_at"),
        "idempotency_records",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_idempotency_records_player_id"),
        "idempotency_records",
        ["player_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove idempotent command responses."""
    op.drop_index(
        op.f("ix_idempotency_records_player_id"),
        table_name="idempotency_records",
    )
    op.drop_index(
        op.f("ix_idempotency_records_expires_at"),
        table_name="idempotency_records",
    )
    op.drop_table("idempotency_records")
