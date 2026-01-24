"""refactor_assessment_questions_to_sheets_row_id

Revision ID: ced2d377fa41
Revises: 2bd1a57c3ec7
Create Date: 2026-01-24 01:03:35.389899

Refactor assessment_questions table to use sheets_row_id as primary key instead of id.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ced2d377fa41'
down_revision: Union[str, None] = '2bd1a57c3ec7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Refactor assessment_questions to use sheets_row_id as primary key."""
    # Step 1: Populate sheets_row_id from id if it's NULL
    op.execute("""
        UPDATE assessment_questions
        SET sheets_row_id = id::text
        WHERE sheets_row_id IS NULL
    """)

    # Step 2: Make sheets_row_id NOT NULL and unique
    op.alter_column("assessment_questions", "sheets_row_id", nullable=False)
    op.create_unique_constraint("uq_assessment_questions_sheets_row_id", "assessment_questions", ["sheets_row_id"])

    # Step 3: Drop old primary key
    op.drop_constraint("assessment_questions_pkey", "assessment_questions", type_="primary")

    # Step 4: Create new primary key on sheets_row_id
    op.create_primary_key("assessment_questions_pkey", "assessment_questions", ["sheets_row_id"])

    # Step 5: Drop the old id column
    op.drop_column("assessment_questions", "id")


def downgrade() -> None:
    """Revert assessment_questions back to using id as primary key."""
    # This is a complex downgrade - would need to restore UUIDs
    # For now, we'll raise an error as this is a destructive migration
    raise NotImplementedError("Downgrade not implemented - this is a destructive migration")
