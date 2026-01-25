"""add_language_domain_to_tasks

Revision ID: d032dc0409e7
Revises: 001_initial
Create Date: 2026-01-25 01:48:04.797085

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd032dc0409e7'
down_revision: str | None = '001_initial'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add language_domain column to tasks table
    op.add_column(
        "tasks",
        sa.Column(
            "language_domain",
            sa.String(),
            nullable=True,
            index=True,
            comment="Language domain: listening, reading, writing, speaking, grammar, vocabulary, pronunciation",
        ),
    )
    # Add check constraint for valid language_domain values
    op.create_check_constraint(
        "check_valid_language_domain",
        "tasks",
        "language_domain IN ('listening', 'reading', 'writing', 'speaking', 'grammar', 'vocabulary', 'pronunciation') OR language_domain IS NULL",
    )


def downgrade() -> None:
    # Remove check constraint (if exists)
    op.execute("ALTER TABLE tasks DROP CONSTRAINT IF EXISTS check_valid_language_domain;")
    # Remove language_domain column (if exists)
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS language_domain;")
