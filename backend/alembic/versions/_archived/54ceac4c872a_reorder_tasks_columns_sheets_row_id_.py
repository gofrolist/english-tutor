"""reorder_tasks_columns_sheets_row_id_first

Revision ID: 54ceac4c872a
Revises: ced2d377fa41
Create Date: 2026-01-24 01:15:48.077857

Reorder tasks table columns to put sheets_row_id first.
PostgreSQL doesn't support direct column reordering, so we recreate the table.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '54ceac4c872a'
down_revision: str | None = 'ced2d377fa41'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Reorder tasks table columns to put sheets_row_id first."""
    # Step 1: Create new table with correct column order
    op.create_table(
        "tasks_new",
        sa.Column("sheets_row_id", sa.String(), primary_key=True, nullable=False, comment="Google Sheets row ID for tracking sync"),
        sa.Column("level", sa.String(), nullable=False, comment="English proficiency level: A1, A2, B1, B2, C1, C2"),
        sa.Column("type", sa.String(), nullable=False, comment="Content type: text, audio, video"),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content_text", sa.String(), nullable=True, comment="Text content for text-type tasks"),
        sa.Column("content_url", sa.String(), nullable=True, comment="URL for audio/video content"),
        sa.Column("explanation", sa.String(), nullable=True, comment="Educational explanation/rules"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft", comment="Task status: draft, published"),
        sa.CheckConstraint("level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')", name="check_valid_level"),
        sa.CheckConstraint("type IN ('text', 'audio', 'video')", name="check_valid_type"),
        sa.CheckConstraint(
            "(type = 'text' AND content_text IS NOT NULL) OR "
            "(type IN ('audio', 'video') AND content_url IS NOT NULL)",
            name="check_content_by_type",
        ),
        sa.CheckConstraint("status IN ('draft', 'published')", name="check_valid_status"),
    )

    # Step 2: Copy data from old table to new table
    op.execute("""
        INSERT INTO tasks_new (
            sheets_row_id, level, type, title, content_text, content_url,
            explanation, created_at, updated_at, status
        )
        SELECT
            sheets_row_id, level, type, title, content_text, content_url,
            explanation, created_at, updated_at, status
        FROM tasks
    """)

    # Step 3: Drop foreign key constraints from questions table (they reference tasks)
    op.drop_constraint("questions_task_id_fkey", "questions", type_="foreignkey")

    # Step 4: Drop old table
    op.drop_index("idx_task_level_status", table_name="tasks")
    op.drop_index("idx_task_type_status", table_name="tasks")
    op.drop_index(op.f("ix_tasks_level"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_status"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_type"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_sheets_row_id"), table_name="tasks")
    op.drop_table("tasks")

    # Step 5: Rename new table to original name
    op.rename_table("tasks_new", "tasks")

    # Step 6: Recreate indexes
    op.create_index("idx_task_level_status", "tasks", ["level", "status"])
    op.create_index("idx_task_type_status", "tasks", ["type", "status"])
    op.create_index(op.f("ix_tasks_level"), "tasks", ["level"])
    op.create_index(op.f("ix_tasks_status"), "tasks", ["status"])
    op.create_index(op.f("ix_tasks_type"), "tasks", ["type"])
    op.create_index(op.f("ix_tasks_sheets_row_id"), "tasks", ["sheets_row_id"])

    # Step 7: Recreate foreign key constraint
    op.create_foreign_key(
        "questions_task_id_fkey",
        "questions",
        "tasks",
        ["task_id"],
        ["sheets_row_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Revert column order (sheets_row_id back to last position)."""
    # This is a complex downgrade - would need to recreate table with original order
    # For now, we'll raise an error as this is a cosmetic change
    raise NotImplementedError("Downgrade not implemented - column order is cosmetic")
