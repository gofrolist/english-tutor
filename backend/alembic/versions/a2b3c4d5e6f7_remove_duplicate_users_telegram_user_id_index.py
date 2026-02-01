"""remove duplicate users telegram_user_id index

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-02-01

Removes duplicate index on users.telegram_user_id.
The table had both ix_users_telegram_user_id (from index=True on column)
and idx_telegram_user_id (explicit Index in __table_args__).
Keep idx_telegram_user_id, drop ix_users_telegram_user_id.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the auto-generated duplicate index on telegram_user_id."""
    op.drop_index(
        "ix_users_telegram_user_id",
        table_name="users",
        if_exists=True,
    )


def downgrade() -> None:
    """Recreate the auto-generated index on telegram_user_id."""
    op.create_index(
        "ix_users_telegram_user_id",
        "users",
        ["telegram_user_id"],
    )
