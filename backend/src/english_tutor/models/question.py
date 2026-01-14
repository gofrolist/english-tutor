"""Question model.

Represents an inquiry within a task.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from src.english_tutor.models.base import Base


def _utcnow_naive() -> datetime:
    """UTC now as a naive datetime (UTC), avoiding deprecated utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Question(Base):
    """Question model representing an inquiry within a task."""

    __tablename__ = "questions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    task_id = Column(Uuid(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    question_text = Column(String, nullable=False)
    answer_options = Column(JSONB, nullable=False, comment="JSON array of answer options")
    correct_answer = Column(
        Integer, nullable=False, comment="Index of correct answer in answer_options"
    )
    weight = Column(Float, nullable=False, default=1.0, comment="Weight for scoring")
    order = Column("order", Integer, nullable=False, comment="Display order within task")
    sheets_row_id = Column(
        String,
        nullable=True,
        index=True,
        comment="Google Sheets row ID for tracking sync",
    )
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False)

    # Relationships
    task = relationship("Task", back_populates="questions")

    __table_args__ = (
        CheckConstraint("weight > 0", name="check_weight_positive"),
        CheckConstraint('"order" > 0', name="check_order_positive"),
        Index("idx_question_task_order", "task_id", "order"),
    )

    def __repr__(self) -> str:
        """String representation of Question."""
        return f"<Question(id={self.id}, task_id={self.task_id}, order={self.order})>"
