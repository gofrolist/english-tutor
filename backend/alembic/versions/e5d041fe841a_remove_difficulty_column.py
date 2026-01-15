"""remove_difficulty_column

Revision ID: e5d041fe841a
Revises: 9b1041eacda2
Create Date: 2026-01-15 16:37:56.827945

Removes the difficulty column from tasks table.
Difficulty is redundant with the level field (A1-C2) which already
indicates task difficulty.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5d041fe841a"
down_revision: str | None = "9b1041eacda2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove difficulty column from tasks table."""
    op.drop_column("tasks", "difficulty")


def downgrade() -> None:
    """Restore difficulty column to tasks table."""
    op.add_column("tasks", sa.Column("difficulty", sa.String(), nullable=True))
