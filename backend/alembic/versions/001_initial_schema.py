"""Initial database schema.

Revision ID: 001_initial
Revises:
Create Date: 2026-01-10

This migration creates the complete initial database schema including:
- Users and assessments tables
- Tasks and questions tables (with Google Sheets integration)
- Progress tracking table
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all database tables for initial schema."""
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_user_id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("current_level", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("idx_telegram_user_id", "users", ["telegram_user_id"], unique=True)

    # Create assessments table
    op.create_table(
        "assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("questions", postgresql.JSONB(), nullable=False),
        sa.Column("answers", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("resulting_level", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="in_progress"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(op.f("ix_assessments_user_id"), "assessments", ["user_id"])

    # Add check constraints for assessments
    op.create_check_constraint(
        "check_score_non_negative",
        "assessments",
        "score >= 0",
    )
    op.create_check_constraint(
        "check_valid_level",
        "assessments",
        "resulting_level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2') OR resulting_level IS NULL",
    )

    # Create tasks table
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("level", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content_text", sa.String(), nullable=True),
        sa.Column("content_audio_url", sa.String(), nullable=True),
        sa.Column("content_video_url", sa.String(), nullable=True),
        sa.Column("explanation", sa.String(), nullable=True),
        sa.Column("difficulty", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("sheets_row_id", sa.String(), nullable=True, comment="Google Sheets row ID for tracking sync"),
        sa.CheckConstraint("level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')", name="check_valid_level"),
        sa.CheckConstraint("type IN ('text', 'audio', 'video')", name="check_valid_type"),
        sa.CheckConstraint(
            "(type = 'text' AND content_text IS NOT NULL) OR "
            "(type = 'audio' AND content_audio_url IS NOT NULL) OR "
            "(type = 'video' AND content_video_url IS NOT NULL)",
            name="check_content_by_type",
        ),
        sa.CheckConstraint("status IN ('draft', 'published')", name="check_valid_status"),
    )
    op.create_index("idx_task_level_status", "tasks", ["level", "status"])
    op.create_index("idx_task_type_status", "tasks", ["type", "status"])
    op.create_index(op.f("ix_tasks_level"), "tasks", ["level"])
    op.create_index(op.f("ix_tasks_status"), "tasks", ["status"])
    op.create_index(op.f("ix_tasks_type"), "tasks", ["type"])
    op.create_index(op.f("ix_tasks_sheets_row_id"), "tasks", ["sheets_row_id"])

    # Create questions table
    op.create_table(
        "questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_text", sa.String(), nullable=False),
        sa.Column("answer_options", postgresql.JSONB(), nullable=False),
        sa.Column("correct_answer", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("sheets_row_id", sa.String(), nullable=True, comment="Google Sheets row ID for tracking sync"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.CheckConstraint("weight > 0", name="check_weight_positive"),
        sa.CheckConstraint('"order" > 0', name="check_order_positive"),
    )
    # Create index with quoted column name for reserved keyword
    op.execute(
        'CREATE INDEX idx_question_task_order ON questions (task_id, "order")'
    )
    op.create_index(op.f("ix_questions_task_id"), "questions", ["task_id"])
    op.create_index(op.f("ix_questions_sheets_row_id"), "questions", ["sheets_row_id"])

    # Create progress table
    op.create_table(
        "progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answers", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("percentage_correct", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.Column("time_taken_seconds", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        # Note: UniqueConstraint removed - using unique index instead (idx_progress_user_task)
        # to avoid duplicate indexes (UniqueConstraint automatically creates an index)
        sa.CheckConstraint("score >= 0", name="check_score_non_negative"),
        sa.CheckConstraint(
            "percentage_correct >= 0 AND percentage_correct <= 100",
            name="check_percentage_range",
        ),
    )
    op.create_index("idx_progress_user_task", "progress", ["user_id", "task_id"], unique=True)
    op.create_index("idx_progress_completed_at", "progress", ["completed_at"])
    op.create_index(op.f("ix_progress_task_id"), "progress", ["task_id"])
    op.create_index(op.f("ix_progress_user_id"), "progress", ["user_id"])


def downgrade() -> None:
    """Drop all database tables."""
    # Drop progress table
    op.drop_index(op.f("ix_progress_user_id"), table_name="progress")
    op.drop_index(op.f("ix_progress_task_id"), table_name="progress")
    op.drop_index("idx_progress_completed_at", table_name="progress")
    op.drop_index("idx_progress_user_task", table_name="progress")
    # Note: No UniqueConstraint to drop (removed to avoid duplicate with unique index)
    op.drop_table("progress")

    # Drop questions table
    op.drop_index(op.f("ix_questions_sheets_row_id"), table_name="questions")
    op.drop_index(op.f("ix_questions_task_id"), table_name="questions")
    op.execute('DROP INDEX IF EXISTS idx_question_task_order')
    op.drop_table("questions")

    # Drop tasks table
    op.drop_index(op.f("ix_tasks_sheets_row_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_type"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_status"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_level"), table_name="tasks")
    op.drop_index("idx_task_type_status", table_name="tasks")
    op.drop_index("idx_task_level_status", table_name="tasks")
    op.drop_table("tasks")

    # Drop assessments table
    op.drop_index(op.f("ix_assessments_user_id"), table_name="assessments")
    op.drop_table("assessments")

    # Drop users table
    op.drop_index("idx_telegram_user_id", table_name="users")
    op.drop_table("users")
