"""Base SQLAlchemy declarative base for models.

This module provides the base class for all database models.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models.

    All models should inherit from this class to ensure they are properly
    registered with SQLAlchemy's declarative system.
    """

    pass
