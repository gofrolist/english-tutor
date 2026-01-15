"""Assessment question model.

Represents a question used for level assessment (separate from task questions).
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

from src.english_tutor.models.base import Base


def _utcnow_naive() -> datetime:
    """UTC now as a naive datetime (UTC), avoiding deprecated utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AssessmentQuestion(Base):
    """Assessment question model for level determination."""

    __tablename__ = "assessment_questions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    level = Column(
        String,
        nullable=False,
        index=True,
        comment="English level this question tests: A1, A2, B1, B2, C1, C2",
    )
    question_text = Column(String, nullable=False)
    answer_options = Column(JSONB, nullable=False, comment="JSON array of answer options")
    correct_answer = Column(
        Integer, nullable=False, comment="Index of correct answer in answer_options"
    )
    weight = Column(Float, nullable=False, default=1.0, comment="Weight for scoring")
    skill_type = Column(
        String,
        nullable=True,
        comment="Type of skill tested: grammar, vocabulary, reading, listening",
    )
    sheets_row_id = Column(
        String,
        nullable=True,
        index=True,
        comment="Google Sheets row ID for tracking sync",
    )
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False)

    __table_args__ = (
        CheckConstraint("level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')", name="check_valid_level"),
        CheckConstraint("weight > 0", name="check_weight_positive"),
        Index("idx_assessment_question_level", "level"),
    )

    def __repr__(self) -> str:
        """String representation of AssessmentQuestion."""
        return f"<AssessmentQuestion(id={self.id}, level={self.level})>"
