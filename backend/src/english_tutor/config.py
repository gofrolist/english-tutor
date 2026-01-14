"""Centralized configuration management for Telegram bot.

This module provides configuration management with environment variable support,
logging setup, and application settings.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

# Load environment variables from .env file
# Look for .env file in the backend directory (parent of src)
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)

# Database configuration (Supabase PostgreSQL)
# Supabase connection string format:
# postgresql://postgres:[PASSWORD]@[PROJECT_REF].supabase.co:5432/postgres
# Or with connection pooler:
# postgresql://postgres:[PASSWORD]@[PROJECT_REF].supabase.co:6543/postgres?pgbouncer=true
DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "postgresql://postgres:password@localhost:5432/postgres"
)
db_engine: Optional[Engine] = None
SessionLocal: Optional[sessionmaker[Session]] = None


def get_database_engine() -> Engine:
    """Create and return SQLAlchemy database engine.

    Returns:
        SQLAlchemy Engine instance configured with DATABASE_URL.
    """
    global db_engine
    if db_engine is None:
        db_engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        )
    return db_engine


def get_session_local() -> sessionmaker[Session]:
    """Create and return SQLAlchemy session factory.

    Returns:
        Session factory configured with database engine.
    """
    global SessionLocal
    if SessionLocal is None:
        engine = get_database_engine()
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal


# Telegram Bot configuration
# Token is loaded but validation is deferred to when it's actually needed
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")


def get_telegram_bot_token() -> str:
    """Get Telegram bot token with validation.

    Returns:
        Telegram bot token string

    Raises:
        ValueError: If token is not set
    """
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required but not set")
    return TELEGRAM_BOT_TOKEN


# Application configuration
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8080"))
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
