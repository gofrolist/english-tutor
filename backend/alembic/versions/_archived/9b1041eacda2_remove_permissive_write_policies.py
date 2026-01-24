"""remove_permissive_write_policies

Revision ID: 9b1041eacda2
Revises: 4d38fbf3441a
Create Date: 2026-01-15 16:10:00.000000

Removes permissive INSERT, UPDATE, and DELETE RLS policies to address Supabase warnings.
Keeps SELECT policies only, as SELECT policies with USING (true) are acceptable
and commonly used for public read access. This satisfies Supabase's security requirements
while avoiding warnings about overly permissive write policies.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9b1041eacda2"
down_revision: str | None = "4d38fbf3441a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# All tables that have RLS policies
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
    """Remove permissive INSERT, UPDATE, and DELETE policies.

    Keeps SELECT policies only, as they are acceptable and commonly used.
    This addresses Supabase warnings about overly permissive write policies
    while maintaining RLS enabled on all tables.
    """
    for table in TABLES:
        # Drop write policies (INSERT, UPDATE, DELETE)
        op.execute(f'DROP POLICY IF EXISTS "allow_authenticated_insert_{table}" ON "{table}";')
        op.execute(f'DROP POLICY IF EXISTS "allow_authenticated_update_{table}" ON "{table}";')
        op.execute(f'DROP POLICY IF EXISTS "allow_authenticated_delete_{table}" ON "{table}";')
        # SELECT policies are kept (they're acceptable and don't trigger warnings)


def downgrade() -> None:
    """Restore permissive INSERT, UPDATE, and DELETE policies."""
    for table in TABLES:
        # Recreate write policies
        op.execute(
            f"""
            CREATE POLICY "allow_authenticated_insert_{table}"
            ON "{table}"
            FOR INSERT
            TO authenticated
            WITH CHECK (true);
            """
        )
        op.execute(
            f"""
            CREATE POLICY "allow_authenticated_update_{table}"
            ON "{table}"
            FOR UPDATE
            TO authenticated
            USING (true)
            WITH CHECK (true);
            """
        )
        op.execute(
            f"""
            CREATE POLICY "allow_authenticated_delete_{table}"
            ON "{table}"
            FOR DELETE
            TO authenticated
            USING (true);
            """
        )
