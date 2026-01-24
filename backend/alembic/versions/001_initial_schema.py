"""Initial database schema.

Revision ID: 001_initial
Revises:
Create Date: 2026-01-24

Consolidated initial database schema with all refactorings applied:
- Users: telegram_user_id as primary key
- Tasks: sheets_row_id as primary key (first column)
- Questions: sheets_row_id as primary key (first column), no order column
- Assessments: sheets_row_id as primary key (first column)
- AssessmentQuestions: sheets_row_id as primary key (first column)
- Progress: id as UUID primary key (unchanged)
- RLS enabled on all tables
- RLS policies (SELECT only) on all tables
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

# All tables that need RLS enabled
TABLES = [
    "users",
    "assessments",
    "assessment_questions",
    "tasks",
    "questions",
    "progress",
    "alembic_version",
]


def upgrade() -> None:
    """Create all database tables with final schema structure."""
    # Create users table
    op.create_table(
        "users",
        sa.Column("telegram_user_id", sa.String(), primary_key=True, nullable=False, index=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("current_level", sa.String(), nullable=True, comment="English proficiency level: A1, A2, B1, B2, C1, C2, or NULL"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("idx_telegram_user_id", "users", ["telegram_user_id"])

    # Create tasks table (sheets_row_id first)
    op.create_table(
        "tasks",
        sa.Column("sheets_row_id", sa.String(), primary_key=True, nullable=False, index=True, comment="Google Sheets row ID for tracking sync"),
        sa.Column("level", sa.String(), nullable=False, index=True, comment="English proficiency level: A1, A2, B1, B2, C1, C2"),
        sa.Column("type", sa.String(), nullable=False, index=True, comment="Content type: text, audio, video"),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content_text", sa.String(), nullable=True, comment="Text content for text-type tasks"),
        sa.Column("content_url", sa.String(), nullable=True, comment="URL for audio/video content"),
        sa.Column("explanation", sa.String(), nullable=True, comment="Educational explanation/rules"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft", index=True, comment="Task status: draft, published"),
        sa.CheckConstraint("level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')", name="check_valid_level"),
        sa.CheckConstraint("type IN ('text', 'audio', 'video')", name="check_valid_type"),
        sa.CheckConstraint(
            "(type = 'text' AND content_text IS NOT NULL) OR "
            "(type IN ('audio', 'video') AND content_url IS NOT NULL)",
            name="check_content_by_type",
        ),
        sa.CheckConstraint("status IN ('draft', 'published')", name="check_valid_status"),
    )
    op.create_index("idx_task_level_status", "tasks", ["level", "status"])
    op.create_index("idx_task_type_status", "tasks", ["type", "status"])

    # Create questions table (sheets_row_id first)
    op.create_table(
        "questions",
        sa.Column("sheets_row_id", sa.String(), primary_key=True, nullable=False, index=True, comment="Google Sheets row ID for tracking sync"),
        sa.Column("task_id", sa.String(), nullable=False, index=True),
        sa.Column("question_text", sa.String(), nullable=False),
        sa.Column("answer_options", postgresql.JSONB(), nullable=False, comment="JSON array of answer options"),
        sa.Column("correct_answer", sa.Integer(), nullable=False, comment="Index of correct answer in answer_options"),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0", comment="Weight for scoring"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.sheets_row_id"], ondelete="CASCADE"),
        sa.CheckConstraint("weight > 0", name="check_weight_positive"),
    )

    # Create assessments table (sheets_row_id first)
    op.create_table(
        "assessments",
        sa.Column("sheets_row_id", sa.String(), primary_key=True, nullable=False, index=True, comment="Google Sheets row ID for tracking sync"),
        sa.Column("user_id", sa.String(), nullable=False, index=True),
        sa.Column("questions", postgresql.JSONB(), nullable=False, comment="JSON array of question sheet_row_ids used in assessment"),
        sa.Column("answers", postgresql.JSONB(), nullable=False, server_default="{}", comment="JSON object mapping question sheet_row_ids to user answers"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("resulting_level", sa.String(), nullable=True, comment="English level determined from assessment: A1, A2, B1, B2, C1, C2"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="in_progress"),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_user_id"]),
        sa.CheckConstraint("score >= 0", name="check_score_non_negative"),
        sa.CheckConstraint(
            "resulting_level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2') OR resulting_level IS NULL",
            name="check_valid_level",
        ),
        sa.CheckConstraint(
            "((status = 'completed' OR status = 'COMPLETED') AND completed_at IS NOT NULL) OR ((status != 'completed' AND status != 'COMPLETED') AND completed_at IS NULL)",
            name="check_completed_at_consistency",
        ),
    )

    # Create assessment_questions table (sheets_row_id first)
    op.create_table(
        "assessment_questions",
        sa.Column("sheets_row_id", sa.String(), primary_key=True, nullable=False, index=True, comment="Google Sheets row ID for tracking sync"),
        sa.Column("level", sa.String(), nullable=False, index=True, comment="English level this question tests: A1, A2, B1, B2, C1, C2"),
        sa.Column("question_text", sa.String(), nullable=False),
        sa.Column("answer_options", postgresql.JSONB(), nullable=False, comment="JSON array of answer options"),
        sa.Column("correct_answer", sa.Integer(), nullable=False, comment="Index of correct answer in answer_options"),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0", comment="Weight for scoring"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')", name="check_valid_level"),
        sa.CheckConstraint("weight > 0", name="check_weight_positive"),
    )
    op.create_index("idx_assessment_question_level", "assessment_questions", ["level"])

    # Create progress table (id as UUID primary key - unchanged)
    op.create_table(
        "progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False, index=True),
        sa.Column("task_id", sa.String(), nullable=False, index=True),
        sa.Column("answers", postgresql.JSONB(), nullable=False, server_default="{}", comment="JSON object mapping question sheet_row_ids to user answers"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("percentage_correct", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.Column("time_taken_seconds", sa.Float(), nullable=True, comment="Duration to complete task (optional)"),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.sheets_row_id"], ondelete="CASCADE"),
        sa.CheckConstraint("score >= 0", name="check_score_non_negative"),
        sa.CheckConstraint(
            "percentage_correct >= 0 AND percentage_correct <= 100",
            name="check_percentage_range",
        ),
    )
    op.create_index("idx_progress_user_task", "progress", ["user_id", "task_id"], unique=True)
    op.create_index("idx_progress_completed_at", "progress", ["completed_at"])

    # Enable RLS on all tables
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY;')

    # Create RLS policies (SELECT only) for all tables
    for table in TABLES:
        op.execute(
            f"""
            CREATE POLICY "allow_authenticated_select_{table}"
            ON "{table}"
            FOR SELECT
            TO authenticated
            USING (true);
            """
        )


def downgrade() -> None:
    """Drop all database tables."""
    # Drop RLS policies
    for table in TABLES:
        op.execute(f'DROP POLICY IF EXISTS "allow_authenticated_select_{table}" ON "{table}";')

    # Drop progress table
    op.drop_index("idx_progress_completed_at", table_name="progress")
    op.drop_index("idx_progress_user_task", table_name="progress")
    op.drop_table("progress")

    # Drop assessment_questions table
    op.drop_index("idx_assessment_question_level", table_name="assessment_questions")
    op.drop_table("assessment_questions")

    # Drop assessments table
    op.drop_table("assessments")

    # Drop questions table
    op.drop_table("questions")

    # Drop tasks table
    op.drop_index("idx_task_type_status", table_name="tasks")
    op.drop_index("idx_task_level_status", table_name="tasks")
    op.drop_table("tasks")

    # Drop users table
    op.drop_index("idx_telegram_user_id", table_name="users")
    op.drop_table("users")
