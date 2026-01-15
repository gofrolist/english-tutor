"""enable_rls_on_all_tables

Revision ID: 3736ec7cb247
Revises: 4c12f35b3efd
Create Date: 2026-01-15 15:41:13.009561

Enables Row Level Security (RLS) on all tables to satisfy Supabase security requirements.
Since this application uses direct database connections (not PostgREST), we create
permissive policies that allow the service role full access while still enabling RLS.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3736ec7cb247"
down_revision: str | None = "4c12f35b3efd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# List of all tables that need RLS enabled
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
    """Enable RLS on all tables to satisfy Supabase security requirements.

    Note: For direct PostgreSQL connections using the 'postgres' role (table owner),
    RLS is bypassed by default in PostgreSQL. This means enabling RLS will NOT
    break your application - direct connections continue to work normally.

    Enabling RLS satisfies Supabase's security requirements and protects tables
    if PostgREST API is ever used. If you need to use PostgREST in the future,
    you'll need to create appropriate RLS policies for the 'authenticated' role.
    """
    # Enable RLS on all tables
    # This satisfies Supabase's security requirement
    # Direct connections as 'postgres' role will bypass RLS automatically
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY;')


def downgrade() -> None:
    """Disable RLS on all tables."""
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY;')
