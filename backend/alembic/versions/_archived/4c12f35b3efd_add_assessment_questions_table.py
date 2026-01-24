"""add_assessment_questions_table

Revision ID: 4c12f35b3efd
Revises: 001_initial
Create Date: 2026-01-15 14:06:16.962086

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '4c12f35b3efd'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create assessment_questions table."""
    op.create_table(
        "assessment_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("level", sa.String(), nullable=False),
        sa.Column("question_text", sa.String(), nullable=False),
        sa.Column("answer_options", postgresql.JSONB(), nullable=False),
        sa.Column("correct_answer", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("skill_type", sa.String(), nullable=True),
        sa.Column("sheets_row_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_assessment_question_level", "assessment_questions", ["level"])
    op.create_index("idx_assessment_question_sheets_row_id", "assessment_questions", ["sheets_row_id"])
    op.create_check_constraint(
        "check_valid_level",
        "assessment_questions",
        "level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')",
    )
    op.create_check_constraint(
        "check_weight_positive",
        "assessment_questions",
        "weight > 0",
    )


def downgrade() -> None:
    """Drop assessment_questions table."""
    op.drop_table("assessment_questions")
