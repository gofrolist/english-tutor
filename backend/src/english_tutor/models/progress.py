"""Progress model.

Represents user performance tracking for completed tasks.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, Float, ForeignKey, Index, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from src.english_tutor.models.base import Base


def _utcnow_naive() -> datetime:
    """UTC now as a naive datetime (UTC), avoiding deprecated utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Progress(Base):
    """Progress model representing user performance on completed tasks."""

    __tablename__ = "progress"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    task_id = Column(Uuid(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    answers = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment="JSON object mapping question IDs to user answers",
    )
    score = Column(Float, nullable=False, default=0.0)
    percentage_correct = Column(Float, nullable=False, default=0.0)
    completed_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    time_taken_seconds = Column(
        Float, nullable=True, comment="Duration to complete task (optional)"
    )

    # Relationships
    user = relationship("User", back_populates="progress_records")
    task = relationship("Task")

    __table_args__ = (
        CheckConstraint("score >= 0", name="check_score_non_negative"),
        CheckConstraint(
            "percentage_correct >= 0 AND percentage_correct <= 100", name="check_percentage_range"
        ),
        Index("idx_progress_user_task", "user_id", "task_id", unique=True),
        Index("idx_progress_completed_at", "completed_at"),
    )

    def __repr__(self) -> str:
        """String representation of Progress."""
        return (
            f"<Progress(id={self.id}, user_id={self.user_id}, "
            f"task_id={self.task_id}, score={self.score})>"
        )
