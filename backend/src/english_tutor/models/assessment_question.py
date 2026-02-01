"""Assessment question model.

Represents a question used for level assessment (separate from task questions).
"""

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB

from src.english_tutor.models.base import Base


def _utcnow_naive() -> datetime:
    """UTC now as a naive datetime (UTC), avoiding deprecated utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AssessmentQuestion(Base):
    """Assessment question model for level determination."""

    __tablename__ = "assessment_questions"

    sheets_row_id = Column(
        String,
        primary_key=True,
        nullable=False,
        index=True,
        comment="Google Sheets row ID for tracking sync",
    )
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
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False)

    __table_args__ = (
        CheckConstraint("level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')", name="check_valid_level"),
        Index("idx_assessment_question_level", "level"),
    )

    def __repr__(self) -> str:
        """String representation of AssessmentQuestion."""
        return f"<AssessmentQuestion(sheets_row_id={self.sheets_row_id}, level={self.level})>"
