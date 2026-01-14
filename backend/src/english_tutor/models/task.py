"""Task model.

Represents a learning activity delivered to users.
"""

import enum
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, Index, String, Uuid
from sqlalchemy.orm import relationship

from src.english_tutor.models.base import Base


def _utcnow_naive() -> datetime:
    """UTC now as a naive datetime (UTC), avoiding deprecated utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TaskStatus(str, enum.Enum):
    """Task status enumeration."""

    DRAFT = "draft"
    PUBLISHED = "published"


class TaskType(str, enum.Enum):
    """Task type enumeration."""

    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"


class Task(Base):
    """Task model representing a learning activity."""

    __tablename__ = "tasks"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    level = Column(
        String,
        nullable=False,
        index=True,
        comment="English proficiency level: A1, A2, B1, B2, C1, C2",
    )
    type = Column(
        String,
        nullable=False,
        index=True,
        comment="Content type: text, audio, video",
    )
    title = Column(String, nullable=False)
    content_text = Column(String, nullable=True, comment="Text content for text-type tasks")
    content_audio_url = Column(String, nullable=True, comment="URL for audio content")
    content_video_url = Column(String, nullable=True, comment="URL for video content")
    explanation = Column(String, nullable=True, comment="Educational explanation/rules")
    difficulty = Column(String, nullable=True, comment="Difficulty indicator (optional)")
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False)
    status = Column(
        String,
        nullable=False,
        default=TaskStatus.DRAFT.value,
        index=True,
        comment="Task status: draft, published",
    )
    sheets_row_id = Column(
        String,
        nullable=True,
        index=True,
        comment="Google Sheets row ID for tracking sync",
    )

    # Relationships
    # Note: order_by uses string reference to avoid circular import
    questions = relationship("Question", back_populates="task", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')", name="check_valid_level"),
        CheckConstraint("type IN ('text', 'audio', 'video')", name="check_valid_type"),
        CheckConstraint(
            "(type = 'text' AND content_text IS NOT NULL) OR "
            "(type = 'audio' AND content_audio_url IS NOT NULL) OR "
            "(type = 'video' AND content_video_url IS NOT NULL)",
            name="check_content_by_type",
        ),
        CheckConstraint("status IN ('draft', 'published')", name="check_valid_status"),
        Index("idx_task_level_status", "level", "status"),
        Index("idx_task_type_status", "type", "status"),
    )

    def __repr__(self) -> str:
        """String representation of Task."""
        return f"<Task(id={self.id}, level={self.level}, type={self.type}, status={self.status})>"
