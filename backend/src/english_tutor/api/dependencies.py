"""Dependencies for FastAPI routes.

This module provides dependency injection functions for FastAPI routes.
"""

from collections.abc import Generator

from sqlalchemy.orm import Session

from src.english_tutor.config import get_session_local
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)


def get_db() -> Generator[Session]:
    """Dependency function to get database session.

    Yields:
        Database session instance.

    Usage:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            ...
    """
    session_local = get_session_local()
    db = session_local()
    try:
        yield db
    finally:
        db.close()
        logger.debug("Database session closed")
