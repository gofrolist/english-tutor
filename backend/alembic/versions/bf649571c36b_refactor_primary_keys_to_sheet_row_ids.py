"""refactor_primary_keys_to_sheet_row_ids

Revision ID: bf649571c36b
Revises: 602b7f7b0bff
Create Date: 2026-01-24 00:01:18.707845

Refactor database schema to use natural keys instead of UUIDs:
- users: Remove id, use telegram_user_id as primary key
- tasks: Remove id, use sheets_row_id as primary key
- questions: Remove id, use sheets_row_id as primary key
- assessments: Remove id, use sheets_row_id as primary key (add column first)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'bf649571c36b'
down_revision: Union[str, None] = '602b7f7b0bff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Refactor primary keys to use natural keys."""
    # Step 1: Add sheets_row_id to assessments table if it doesn't exist
    op.add_column(
        "assessments",
        sa.Column("sheets_row_id", sa.String(), nullable=True, comment="Google Sheets row ID for tracking sync"),
    )
    op.create_index("ix_assessments_sheets_row_id", "assessments", ["sheets_row_id"])

    # Step 2: Populate sheets_row_id for all tables using existing UUIDs as strings
    # This ensures all rows have a value before making it NOT NULL
    op.execute("""
        UPDATE assessments
        SET sheets_row_id = id::text
        WHERE sheets_row_id IS NULL
    """)
    op.execute("""
        UPDATE tasks
        SET sheets_row_id = id::text
        WHERE sheets_row_id IS NULL
    """)
    op.execute("""
        UPDATE questions
        SET sheets_row_id = id::text
        WHERE sheets_row_id IS NULL
    """)

    # Step 3: Make sheets_row_id NOT NULL and unique for all tables
    op.alter_column("assessments", "sheets_row_id", nullable=False)
    op.create_unique_constraint("uq_assessments_sheets_row_id", "assessments", ["sheets_row_id"])

    op.alter_column("tasks", "sheets_row_id", nullable=False)
    op.create_unique_constraint("uq_tasks_sheets_row_id", "tasks", ["sheets_row_id"])

    op.alter_column("questions", "sheets_row_id", nullable=False)
    op.create_unique_constraint("uq_questions_sheets_row_id", "questions", ["sheets_row_id"])

    # telegram_user_id is already unique, but ensure it's NOT NULL
    op.alter_column("users", "telegram_user_id", nullable=False)

    # Step 4: Update JSONB fields that store IDs
    # Update assessments.questions (array of question IDs) to use sheets_row_id
    # Use COALESCE to handle cases where some question IDs don't exist
    # Only update rows where at least one question can be mapped
    op.execute("""
        UPDATE assessments a
        SET questions = COALESCE(
            (
                SELECT jsonb_agg(q.sheets_row_id)
                FROM jsonb_array_elements_text(a.questions) AS old_id
                JOIN questions q ON q.id::text = old_id
            ),
            a.questions  -- Keep original if no questions can be mapped
        )
        WHERE a.questions IS NOT NULL
        AND EXISTS (
            SELECT 1
            FROM jsonb_array_elements_text(a.questions) AS old_id
            JOIN questions q ON q.id::text = old_id
        )
    """)

    # Update assessments.answers (object mapping question IDs to answers) to use sheets_row_id
    # Use COALESCE to handle cases where some question IDs don't exist
    op.execute("""
        UPDATE assessments a
        SET answers = COALESCE(
            (
                SELECT jsonb_object_agg(q.sheets_row_id, a.answers->>old_id::text)
                FROM jsonb_object_keys(a.answers) AS old_id
                JOIN questions q ON q.id::text = old_id
            ),
            a.answers  -- Keep original if no questions can be mapped
        )
        WHERE a.answers IS NOT NULL
        AND EXISTS (
            SELECT 1
            FROM jsonb_object_keys(a.answers) AS old_id
            JOIN questions q ON q.id::text = old_id
        )
    """)

    # Update progress.answers (object mapping question IDs to answers) to use sheets_row_id
    # Use COALESCE to handle cases where some question IDs don't exist
    op.execute("""
        UPDATE progress p
        SET answers = COALESCE(
            (
                SELECT jsonb_object_agg(q.sheets_row_id, p.answers->>old_id::text)
                FROM jsonb_object_keys(p.answers) AS old_id
                JOIN questions q ON q.id::text = old_id
            ),
            p.answers  -- Keep original if no questions can be mapped
        )
        WHERE p.answers IS NOT NULL
        AND EXISTS (
            SELECT 1
            FROM jsonb_object_keys(p.answers) AS old_id
            JOIN questions q ON q.id::text = old_id
        )
    """)

    # Step 5: Drop foreign key constraints and indexes that reference old primary keys
    op.drop_constraint("progress_task_id_fkey", "progress", type_="foreignkey")
    op.drop_constraint("progress_user_id_fkey", "progress", type_="foreignkey")
    op.drop_constraint("questions_task_id_fkey", "questions", type_="foreignkey")
    op.drop_constraint("assessments_user_id_fkey", "assessments", type_="foreignkey")

    # Step 6: Change foreign key columns from UUID to String
    op.alter_column("progress", "user_id", type_=sa.String(), postgresql_using="user_id::text")
    op.alter_column("progress", "task_id", type_=sa.String(), postgresql_using="task_id::text")
    op.alter_column("questions", "task_id", type_=sa.String(), postgresql_using="task_id::text")
    op.alter_column("assessments", "user_id", type_=sa.String(), postgresql_using="user_id::text")

    # Step 7: Update foreign key values to use new primary keys
    op.execute("""
        UPDATE progress p
        SET user_id = u.telegram_user_id
        FROM users u
        WHERE p.user_id = u.id::text
    """)
    op.execute("""
        UPDATE progress p
        SET task_id = t.sheets_row_id
        FROM tasks t
        WHERE p.task_id = t.id::text
    """)
    op.execute("""
        UPDATE questions q
        SET task_id = t.sheets_row_id
        FROM tasks t
        WHERE q.task_id = t.id::text
    """)
    op.execute("""
        UPDATE assessments a
        SET user_id = u.telegram_user_id
        FROM users u
        WHERE a.user_id = u.id::text
    """)

    # Step 8: Drop old primary keys and create new ones
    op.drop_constraint("users_pkey", "users", type_="primary")
    op.drop_constraint("tasks_pkey", "tasks", type_="primary")
    op.drop_constraint("questions_pkey", "questions", type_="primary")
    op.drop_constraint("assessments_pkey", "assessments", type_="primary")

    op.create_primary_key("users_pkey", "users", ["telegram_user_id"])
    op.create_primary_key("tasks_pkey", "tasks", ["sheets_row_id"])
    op.create_primary_key("questions_pkey", "questions", ["sheets_row_id"])
    op.create_primary_key("assessments_pkey", "assessments", ["sheets_row_id"])

    # Step 9: Recreate foreign key constraints with new types
    op.create_foreign_key(
        "progress_user_id_fkey",
        "progress",
        "users",
        ["user_id"],
        ["telegram_user_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "progress_task_id_fkey",
        "progress",
        "tasks",
        ["task_id"],
        ["sheets_row_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "questions_task_id_fkey",
        "questions",
        "tasks",
        ["task_id"],
        ["sheets_row_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "assessments_user_id_fkey",
        "assessments",
        "users",
        ["user_id"],
        ["telegram_user_id"],
    )

    # Step 10: Drop old id columns
    op.drop_column("users", "id")
    op.drop_column("tasks", "id")
    op.drop_column("questions", "id")
    op.drop_column("assessments", "id")


def downgrade() -> None:
    """Revert primary keys back to UUIDs."""
    # This is a complex downgrade - would need to restore UUIDs
    # For now, we'll raise an error as this is a destructive migration
    raise NotImplementedError("Downgrade not implemented - this is a destructive migration")
