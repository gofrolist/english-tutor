"""remove_skill_type_from_assessment_questions

Revision ID: 602b7f7b0bff
Revises: e5d041fe841a
Create Date: 2026-01-20 11:38:22.311043

Remove skill_type column from assessment_questions table.
This field was stored but never used in the application logic.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '602b7f7b0bff'
down_revision: Union[str, None] = 'e5d041fe841a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove skill_type column from assessment_questions table."""
    op.drop_column("assessment_questions", "skill_type")


def downgrade() -> None:
    """Add skill_type column back to assessment_questions table."""
    op.add_column(
        "assessment_questions",
        sa.Column("skill_type", sa.String(), nullable=True)
    )
