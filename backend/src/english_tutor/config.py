"""Centralized configuration management for Telegram bot.

This module provides configuration management with environment variable support,
logging setup, and application settings.
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

from src.english_tutor.utils.logger import setup_logging

@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    database_url: str
    sql_echo: bool
    telegram_bot_token: str
    api_host: str
    api_port: int
    debug: bool
    telegram_webhook_url: Optional[str]
    media_cache_dir: str

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from environment variables and .env file."""
        env_path = Path(__file__).parent.parent.parent / ".env"
        load_dotenv(dotenv_path=env_path, override=False)

        return cls(
            database_url=os.getenv(
                "DATABASE_URL", "postgresql://postgres:password@localhost:5432/postgres"
            ),
            sql_echo=os.getenv("SQL_ECHO", "false").lower() == "true",
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            api_host=os.getenv("API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "8080")),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            telegram_webhook_url=os.getenv("TELEGRAM_WEBHOOK_URL") or None,
            media_cache_dir=os.getenv("MEDIA_CACHE_DIR", "/app/data/media_cache"),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    settings = Settings.load()
    log_level = "DEBUG" if settings.debug else "INFO"
    setup_logging(log_level=log_level)
    return settings


db_engine: Optional[Engine] = None
SessionLocal: Optional[sessionmaker[Session]] = None


def get_database_engine() -> Engine:
    """Create and return SQLAlchemy database engine.

    Returns:
        SQLAlchemy Engine instance configured with DATABASE_URL.
    """
    global db_engine
    if db_engine is None:
        settings = get_settings()
        db_engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            echo=settings.sql_echo,
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


def get_telegram_bot_token() -> str:
    """Get Telegram bot token with validation.

    Returns:
        Telegram bot token string

    Raises:
        ValueError: If token is not set
    """
    token = get_settings().telegram_bot_token
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required but not set")
    return token
