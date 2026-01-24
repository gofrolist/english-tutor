"""merge_content_urls_and_remove_question_order

Revision ID: 2bd1a57c3ec7
Revises: bf649571c36b
Create Date: 2026-01-24 00:30:00.000000

Merge content_audio_url and content_video_url into content_url.
Remove questions.order column and order by sheets_row_id instead.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2bd1a57c3ec7'
down_revision: Union[str, None] = 'bf649571c36b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge content URLs and remove question order."""
    # Step 1: Add content_url column to tasks
    op.add_column(
        "tasks",
        sa.Column("content_url", sa.String(), nullable=True, comment="URL for audio/video content"),
    )

    # Step 2: Migrate data from content_audio_url and content_video_url to content_url
    op.execute("""
        UPDATE tasks
        SET content_url = COALESCE(content_audio_url, content_video_url)
        WHERE content_audio_url IS NOT NULL OR content_video_url IS NOT NULL
    """)

    # Step 3: Drop old check constraint
    op.drop_constraint("check_content_by_type", "tasks", type_="check")

    # Step 4: Drop old columns
    op.drop_column("tasks", "content_audio_url")
    op.drop_column("tasks", "content_video_url")

    # Step 5: Add new check constraint
    op.create_check_constraint(
        "check_content_by_type",
        "tasks",
        "(type = 'text' AND content_text IS NOT NULL) OR "
        "(type IN ('audio', 'video') AND content_url IS NOT NULL)",
    )

    # Step 6: Make content_url NOT NULL for audio/video tasks (after migration)
    # Note: We can't make it NOT NULL directly if there are NULL values,
    # but the constraint above ensures new rows follow the rule

    # Step 7: Drop index and constraint related to questions.order
    op.drop_index("idx_question_task_order", table_name="questions")
    op.drop_constraint("check_order_positive", "questions", type_="check")

    # Step 8: Drop order column from questions
    op.drop_column("questions", "order")


def downgrade() -> None:
    """Revert changes - restore separate URLs and order column."""
    # Add back order column
    op.add_column(
        "questions",
        sa.Column("order", sa.Integer(), nullable=False, server_default="1", comment="Display order within task"),
    )
    op.create_check_constraint("check_order_positive", "questions", '"order" > 0')
    op.create_index("idx_question_task_order", "questions", ["task_id", "order"])

    # Add back content_audio_url and content_video_url
    op.add_column(
        "tasks",
        sa.Column("content_audio_url", sa.String(), nullable=True, comment="URL for audio content"),
    )
    op.add_column(
        "tasks",
        sa.Column("content_video_url", sa.String(), nullable=True, comment="URL for video content"),
    )

    # Migrate data back (split content_url based on task type)
    op.execute("""
        UPDATE tasks
        SET content_audio_url = CASE WHEN type = 'audio' THEN content_url ELSE NULL END,
            content_video_url = CASE WHEN type = 'video' THEN content_url ELSE NULL END
        WHERE content_url IS NOT NULL
    """)

    # Drop new constraint and add old one
    op.drop_constraint("check_content_by_type", "tasks", type_="check")
    op.create_check_constraint(
        "check_content_by_type",
        "tasks",
        "(type = 'text' AND content_text IS NOT NULL) OR "
        "(type = 'audio' AND content_audio_url IS NOT NULL) OR "
        "(type = 'video' AND content_video_url IS NOT NULL)",
    )

    # Drop content_url column
    op.drop_column("tasks", "content_url")
