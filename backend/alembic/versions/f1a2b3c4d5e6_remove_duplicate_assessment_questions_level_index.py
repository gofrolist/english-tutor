"""remove duplicate assessment_questions level index

Revision ID: f1a2b3c4d5e6
Revises: e8f2a1b4c5d6
Create Date: 2026-02-01

Removes duplicate index on assessment_questions.level.
The table had both ix_assessment_questions_level (from index=True on column)
and idx_assessment_question_level (explicit Index in __table_args__).
Keep idx_assessment_question_level, drop ix_assessment_questions_level.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e8f2a1b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the auto-generated duplicate index on level."""
    op.drop_index(
        "ix_assessment_questions_level",
        table_name="assessment_questions",
        if_exists=True,
    )


def downgrade() -> None:
    """Recreate the auto-generated index on level."""
    op.create_index(
        "ix_assessment_questions_level",
        "assessment_questions",
        ["level"],
    )
