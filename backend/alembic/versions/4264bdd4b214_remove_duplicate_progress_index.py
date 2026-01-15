"""remove_duplicate_progress_index

Revision ID: 4264bdd4b214
Revises: 3736ec7cb247
Create Date: 2026-01-15 15:47:24.206323

Removes duplicate index on progress table.
The table has both a UniqueConstraint (uq_user_task_progress) and
a unique index (idx_progress_user_task) on the same columns (user_id, task_id).
Since UniqueConstraint automatically creates an index in PostgreSQL,
we remove the UniqueConstraint and keep the explicit index to match the model.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4264bdd4b214"
down_revision: str | None = "3736ec7cb247"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove duplicate UniqueConstraint, keeping the unique index."""
    # Drop the UniqueConstraint (uq_user_task_progress)
    # The unique index (idx_progress_user_task) already provides uniqueness
    op.drop_constraint("uq_user_task_progress", "progress", type_="unique")


def downgrade() -> None:
    """Restore the UniqueConstraint."""
    # Recreate the UniqueConstraint
    op.create_unique_constraint("uq_user_task_progress", "progress", ["user_id", "task_id"])
