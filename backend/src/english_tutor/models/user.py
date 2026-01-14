"""User model.

Represents a learner using the bot.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Index, String, Uuid
from sqlalchemy.orm import relationship

from src.english_tutor.models.base import Base


def _utcnow_naive() -> datetime:
    """UTC now as a naive datetime (UTC), avoiding deprecated utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    """User model representing a learner using the bot."""

    __tablename__ = "users"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    telegram_user_id = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, nullable=True)
    current_level = Column(
        String,
        nullable=True,
        comment="English proficiency level: A1, A2, B1, B2, C1, C2, or NULL",
    )
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    assessments = relationship("Assessment", back_populates="user", cascade="all, delete-orphan")
    progress_records = relationship("Progress", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (Index("idx_telegram_user_id", "telegram_user_id"),)

    def __repr__(self) -> str:
        """String representation of User."""
        return f"<User(id={self.id}, telegram_user_id={self.telegram_user_id}, level={self.current_level})>"
