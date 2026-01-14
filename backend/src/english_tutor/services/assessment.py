"""Assessment service.

Business logic for assessment quiz, scoring, and level determination.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.english_tutor.models.assessment import Assessment, AssessmentStatus
from src.english_tutor.utils.exceptions import AssessmentError
from src.english_tutor.utils.logger import get_logger, log_quiz_submission, log_user_interaction

logger = get_logger(__name__)


class AssessmentService:
    """Service for managing assessments."""

    # Level thresholds based on score (0.0 to 1.0)
    # Ranges are [min, max) - score >= min and score < max
    # For boundary values, the lower bound is inclusive, upper bound is exclusive
    # C2 includes 1.0 by using 1.01 as upper bound
    LEVEL_THRESHOLDS = {
        "A1": (0.0, 0.20),  # 0.0 <= score < 0.20
        "A2": (0.20, 0.40),  # 0.20 <= score < 0.40
        "B1": (0.40, 0.60),  # 0.40 <= score < 0.60
        "B2": (0.60, 0.80),  # 0.60 <= score < 0.80
        "C1": (0.80, 0.95),  # 0.80 <= score < 0.95
        "C2": (0.95, 1.01),  # 0.95 <= score <= 1.0 (using 1.01 to include 1.0)
    }

    def calculate_score(
        self,
        questions: list[dict[str, Any]],
        answers: dict[str, Any],
    ) -> float:
        """Calculate assessment score from weighted answers.

        Args:
            questions: List of question dictionaries with id, weight, correct_answer.
            answers: Dictionary mapping question IDs to user answers.

        Returns:
            Score as float between 0.0 and 1.0.
        """
        total_weight = 0.0
        earned_weight = 0.0

        for question in questions:
            question_id = question["id"]
            weight = question.get("weight", 1.0)
            correct_answer = question["correct_answer"]

            total_weight += weight

            if question_id in answers:
                user_answer = answers[question_id]
                if user_answer == correct_answer:
                    earned_weight += weight

        if total_weight == 0:
            return 0.0

        return earned_weight / total_weight

    def determine_level(self, score: float) -> str:
        """Determine English level from assessment score.

        Args:
            score: Score between 0.0 and 1.0.

        Returns:
            English level (A1, A2, B1, B2, C1, C2).

        Raises:
            AssessmentError: If score is outside valid range.
        """
        if score < 0.0 or score > 1.0:
            raise AssessmentError(f"Invalid score: {score}. Must be between 0.0 and 1.0")

        for level, (min_score, max_score) in self.LEVEL_THRESHOLDS.items():
            if min_score <= score < max_score:
                return level

        raise AssessmentError(f"Could not determine level for score: {score}")

    async def start_assessment(
        self,
        user_id: UUID,
        db: Session,
        question_ids: list[str] | None = None,
    ) -> Assessment:
        """Start a new assessment for a user.

        Args:
            user_id: User UUID.
            db: Database session.
            question_ids: Optional list of question IDs to use. If None, will be selected.

        Returns:
            Created Assessment instance.
        """
        # TODO: Select questions if question_ids is None
        # For now, use provided question_ids or empty list
        if question_ids is None:
            question_ids = []

        assessment = Assessment(
            user_id=user_id,
            questions=question_ids,
            answers={},
            score=0.0,
            status=AssessmentStatus.IN_PROGRESS,
        )

        db.add(assessment)
        db.commit()
        db.refresh(assessment)

        logger.info(
            "Assessment started",
            extra={
                "assessment_id": str(assessment.id),
                "user_id": str(user_id),
                "question_count": len(question_ids),
            },
        )

        log_user_interaction(
            logger,
            str(user_id),
            "assessment_started",
            assessment_id=str(assessment.id),
        )

        return assessment

    async def complete_assessment(
        self,
        assessment_id: UUID,
        answers: dict[str, Any],
        score: float,
        level: str,
        db: Session,
    ) -> Assessment:
        """Complete an assessment with answers and determine level.

        Args:
            assessment_id: Assessment UUID.
            answers: Dictionary mapping question IDs to user answers.
            score: Calculated score.
            level: Determined English level.
            db: Database session.

        Returns:
            Updated Assessment instance.
        """
        assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
        if not assessment:
            raise AssessmentError(f"Assessment not found: {assessment_id}")

        assessment.answers = answers
        assessment.score = score
        assessment.resulting_level = level
        assessment.status = AssessmentStatus.COMPLETED
        assessment.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

        db.commit()
        db.refresh(assessment)

        log_quiz_submission(
            logger,
            str(assessment.user_id),
            str(assessment_id),
            score,
            level=level,
        )

        logger.info(
            "Assessment completed",
            extra={
                "assessment_id": str(assessment_id),
                "user_id": str(assessment.user_id),
                "score": score,
                "level": level,
            },
        )

        return assessment

    async def abandon_assessment(
        self,
        assessment_id: UUID,
        db: Session,
    ) -> Assessment:
        """Abandon an in-progress assessment.

        Args:
            assessment_id: Assessment UUID.
            db: Database session.

        Returns:
            Updated Assessment instance.
        """
        assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
        if not assessment:
            raise AssessmentError(f"Assessment not found: {assessment_id}")

        assessment.status = AssessmentStatus.ABANDONED

        db.commit()
        db.refresh(assessment)

        logger.info(
            "Assessment abandoned",
            extra={
                "assessment_id": str(assessment_id),
                "user_id": str(assessment.user_id),
            },
        )

        return assessment
