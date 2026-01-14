"""Pytest configuration and fixtures.

Shared fixtures for all tests.
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.sqlite import base as sqlite_base
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from src.english_tutor.models.assessment import Assessment  # noqa: F401

# Import all models to ensure relationships are registered
from src.english_tutor.models.base import Base
from src.english_tutor.models.progress import Progress  # noqa: F401
from src.english_tutor.models.question import Question  # noqa: F401
from src.english_tutor.models.task import Task  # noqa: F401
from src.english_tutor.models.user import User  # noqa: F401


# Patch SQLite to support JSONB by mapping it to JSON
def _patch_sqlite_jsonb():
    """Patch SQLite type compiler to handle JSONB as JSON."""

    def visit_jsonb(self, type_, **kw):
        return "JSON"

    if not hasattr(sqlite_base.SQLiteTypeCompiler, "visit_JSONB"):
        sqlite_base.SQLiteTypeCompiler.visit_JSONB = visit_jsonb


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable foreign keys for SQLite."""
    if "sqlite" in str(dbapi_conn):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture(scope="function")
def db_session():
    """Create a database session for testing."""
    # Patch JSONB for SQLite compatibility
    _patch_sqlite_jsonb()

    # Use in-memory SQLite for testing with a named database
    # Using ":memory:" creates a new database per connection, so we use a file-based approach
    # or ensure we use the same connection. For tests, we'll use a file that gets cleaned up.
    import os
    import tempfile

    db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    db_path = db_file.name
    db_file.close()

    try:
        # check_same_thread=False allows SQLite to work with FastAPI TestClient
        engine = create_engine(
            f"sqlite:///{db_path}", echo=False, connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(engine)
        session_local = sessionmaker(bind=engine)
        session = session_local()
        try:
            yield session
        finally:
            session.close()
            Base.metadata.drop_all(engine)
            engine.dispose()
    finally:
        # Clean up the temporary database file
        if os.path.exists(db_path):
            os.unlink(db_path)
