"""add_rls_policies_for_all_tables

Revision ID: fcd9b6778419
Revises: 4264bdd4b214
Create Date: 2026-01-15 15:50:00.000000

Adds RLS policies to all tables to satisfy Supabase security requirements.
Supabase requires RLS enabled on all public tables, including system tables
like alembic_version. Creates permissive policies for authenticated role
on all tables to allow access through PostgREST if used in the future.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fcd9b6778419"
down_revision: str | None = "4264bdd4b214"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# All tables that need RLS policies (including alembic_version)
TABLES_WITH_POLICIES = [
    "users",
    "assessments",
    "assessment_questions",
    "tasks",
    "questions",
    "progress",
    "alembic_version",
]


def upgrade() -> None:
    """Add RLS policies to all tables including alembic_version.

    - Creates permissive policies for authenticated role on all tables
    - Supabase requires RLS enabled on all public tables, including system tables
    - Supabase always has the 'authenticated' role (used by PostgREST)
    - These policies allow access through PostgREST if used in the future
    """
    # Create policies for all tables (including alembic_version)
    # Supabase always has the 'authenticated' role (used by PostgREST)
    # These policies allow access through PostgREST if used in the future
    # Note: PostgreSQL doesn't support IF NOT EXISTS for CREATE POLICY,
    # so we drop policies first (if they exist) then create them
    for table in TABLES_WITH_POLICIES:
        # Drop existing policies if they exist (safe to run multiple times)
        op.execute(f'DROP POLICY IF EXISTS "allow_authenticated_select_{table}" ON "{table}";')
        op.execute(f'DROP POLICY IF EXISTS "allow_authenticated_insert_{table}" ON "{table}";')
        op.execute(f'DROP POLICY IF EXISTS "allow_authenticated_update_{table}" ON "{table}";')
        op.execute(f'DROP POLICY IF EXISTS "allow_authenticated_delete_{table}" ON "{table}";')

        # Create policies
        op.execute(
            f"""
            CREATE POLICY "allow_authenticated_select_{table}"
            ON "{table}"
            FOR SELECT
            TO authenticated
            USING (true);
            """
        )
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


def downgrade() -> None:
    """Remove RLS policies from all tables."""
    # Drop policies for all tables
    for table in TABLES_WITH_POLICIES:
        op.execute(f'DROP POLICY IF EXISTS "allow_authenticated_select_{table}" ON "{table}";')
        op.execute(f'DROP POLICY IF EXISTS "allow_authenticated_insert_{table}" ON "{table}";')
        op.execute(f'DROP POLICY IF EXISTS "allow_authenticated_update_{table}" ON "{table}";')
        op.execute(f'DROP POLICY IF EXISTS "allow_authenticated_delete_{table}" ON "{table}";')
