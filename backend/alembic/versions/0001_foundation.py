"""Establish the migration baseline.

Revision ID: 0001_foundation
Revises:
Create Date: 2026-07-10
"""

from collections.abc import Sequence

revision: str = "0001_foundation"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the foundation revision before domain tables are introduced."""


def downgrade() -> None:
    """Remove the foundation revision."""
