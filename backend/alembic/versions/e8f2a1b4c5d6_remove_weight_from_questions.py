"""remove weight from questions and assessment_questions

Revision ID: e8f2a1b4c5d6
Revises: d032dc0409e7
Create Date: 2026-02-01

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8f2a1b4c5d6"
down_revision: str | None = "d032dc0409e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # questions: drop constraint then column (IF EXISTS for idempotency)
    op.execute("ALTER TABLE questions DROP CONSTRAINT IF EXISTS check_weight_positive;")
    op.execute("ALTER TABLE questions DROP COLUMN IF EXISTS weight;")

    # assessment_questions: drop constraint then column
    op.execute(
        "ALTER TABLE assessment_questions DROP CONSTRAINT IF EXISTS check_weight_positive;"
    )
    op.execute("ALTER TABLE assessment_questions DROP COLUMN IF EXISTS weight;")


def downgrade() -> None:
    from sqlalchemy import sa

    # assessment_questions: add column then constraint
    op.add_column(
        "assessment_questions",
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.create_check_constraint(
        "check_weight_positive", "assessment_questions", "weight > 0"
    )

    # questions: add column then constraint
    op.add_column(
        "questions",
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.create_check_constraint("check_weight_positive", "questions", "weight > 0")
