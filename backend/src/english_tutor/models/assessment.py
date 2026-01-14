"""Assessment model.

Represents an evaluation session to determine English level.
"""

import enum
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
    Uuid,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from src.english_tutor.models.base import Base


def _utcnow_naive() -> datetime:
    """UTC now as a naive datetime (UTC), avoiding deprecated utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AssessmentStatus(str, enum.Enum):
    """Assessment status enumeration."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class Assessment(Base):
    """Assessment model representing an evaluation session."""

    __tablename__ = "assessments"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    questions = Column(
        JSONB, nullable=False, comment="JSON array of question IDs used in assessment"
    )
    answers = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment="JSON object mapping question IDs to user answers",
    )
    score = Column(Float, nullable=False, default=0.0)
    resulting_level = Column(
        String,
        nullable=True,
        comment="English level determined from assessment: A1, A2, B1, B2, C1, C2",
    )
    started_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(
        SQLEnum(AssessmentStatus),
        nullable=False,
        default=AssessmentStatus.IN_PROGRESS,
    )

    # Relationships
    user = relationship("User", back_populates="assessments")

    __table_args__ = (
        CheckConstraint("score >= 0", name="check_score_non_negative"),
        CheckConstraint(
            "resulting_level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2') OR resulting_level IS NULL",
            name="check_valid_level",
        ),
        CheckConstraint(
            "((status = 'completed' OR status = 'COMPLETED') AND completed_at IS NOT NULL) OR ((status != 'completed' AND status != 'COMPLETED') AND completed_at IS NULL)",
            name="check_completed_at_consistency",
        ),
    )

    def __repr__(self) -> str:
        """String representation of Assessment."""
        return (
            f"<Assessment(id={self.id}, user_id={self.user_id}, "
            f"status={self.status}, level={self.resulting_level})>"
        )
