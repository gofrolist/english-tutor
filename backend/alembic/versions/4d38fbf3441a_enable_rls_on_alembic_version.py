"""enable_rls_on_alembic_version

Revision ID: 4d38fbf3441a
Revises: fcd9b6778419
Create Date: 2026-01-15 16:00:00.000000

Enables RLS on alembic_version table and adds policies.
Supabase requires RLS enabled on all public tables, including system tables.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4d38fbf3441a"
down_revision: str | None = "fcd9b6778419"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable RLS on alembic_version and add policies.

    Supabase requires RLS enabled on all public tables, including system tables.
    Creates permissive policies for authenticated role to allow access.
    """
    # Enable RLS on alembic_version
    op.execute('ALTER TABLE "alembic_version" ENABLE ROW LEVEL SECURITY;')

    # Drop existing policies if they exist (safe to run multiple times)
    op.execute('DROP POLICY IF EXISTS "allow_authenticated_select_alembic_version" ON "alembic_version";')
    op.execute('DROP POLICY IF EXISTS "allow_authenticated_insert_alembic_version" ON "alembic_version";')
    op.execute('DROP POLICY IF EXISTS "allow_authenticated_update_alembic_version" ON "alembic_version";')
    op.execute('DROP POLICY IF EXISTS "allow_authenticated_delete_alembic_version" ON "alembic_version";')

    # Create policies
    op.execute(
        """
        CREATE POLICY "allow_authenticated_select_alembic_version"
        ON "alembic_version"
        FOR SELECT
        TO authenticated
        USING (true);
        """
    )
    op.execute(
        """
        CREATE POLICY "allow_authenticated_insert_alembic_version"
        ON "alembic_version"
        FOR INSERT
        TO authenticated
        WITH CHECK (true);
        """
    )
    op.execute(
        """
        CREATE POLICY "allow_authenticated_update_alembic_version"
        ON "alembic_version"
        FOR UPDATE
        TO authenticated
        USING (true)
        WITH CHECK (true);
        """
    )
    op.execute(
        """
        CREATE POLICY "allow_authenticated_delete_alembic_version"
        ON "alembic_version"
        FOR DELETE
        TO authenticated
        USING (true);
        """
    )


def downgrade() -> None:
    """Disable RLS on alembic_version and remove policies."""
    # Drop policies
    op.execute('DROP POLICY IF EXISTS "allow_authenticated_select_alembic_version" ON "alembic_version";')
    op.execute('DROP POLICY IF EXISTS "allow_authenticated_insert_alembic_version" ON "alembic_version";')
    op.execute('DROP POLICY IF EXISTS "allow_authenticated_update_alembic_version" ON "alembic_version";')
    op.execute('DROP POLICY IF EXISTS "allow_authenticated_delete_alembic_version" ON "alembic_version";')

    # Disable RLS
    op.execute('ALTER TABLE "alembic_version" DISABLE ROW LEVEL SECURITY;')
