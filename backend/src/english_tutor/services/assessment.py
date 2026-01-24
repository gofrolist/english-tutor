"""Assessment service.

Business logic for assessment quiz, scoring, and level determination.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.english_tutor.models.assessment import Assessment, AssessmentStatus
from src.english_tutor.models.assessment_question import AssessmentQuestion
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
        user_id: str,
        db: Session,
        question_ids: list[str] | None = None,
        sheets_row_id: str | None = None,
    ) -> Assessment:
        """Start a new assessment for a user.

        Args:
            user_id: User telegram_user_id.
            db: Database session.
            question_ids: Optional list of question sheets_row_ids to use. If None, will be selected.
            sheets_row_id: Optional sheets_row_id for the assessment. If None, will be generated.

        Returns:
            Created Assessment instance.
        """
        # Select questions if question_ids is None
        if question_ids is None:
            question_ids = self._select_assessment_questions(db)

        # Generate sheets_row_id if not provided (use a timestamp-based ID)
        if sheets_row_id is None:
            import time

            sheets_row_id = f"assessment_{int(time.time() * 1000)}"

        assessment = Assessment(
            sheets_row_id=sheets_row_id,
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
                "assessment_id": assessment.sheets_row_id,
                "user_id": user_id,
                "question_count": len(question_ids),
            },
        )

        log_user_interaction(
            logger,
            user_id,
            "assessment_started",
            assessment_id=assessment.sheets_row_id,
        )

        return assessment

    def _select_assessment_questions(self, db: Session) -> list[str]:
        """Select all assessment questions from the database.

        Strategy:
        - Select all questions from all levels (A1-C2)
        - Return question sheets_row_ids as strings for JSON storage, ordered sequentially by sheets_row_id

        Args:
            db: Database session

        Returns:
            List of question sheets_row_ids as strings, ordered sequentially by sheets_row_id
        """
        # Get all questions ordered by sheets_row_id
        selected_questions = (
            db.query(AssessmentQuestion)
            .filter(
                AssessmentQuestion.sheets_row_id.isnot(None),  # Only include synced questions
            )
            .order_by(AssessmentQuestion.sheets_row_id)
            .all()
        )

        # Extract question sheets_row_ids
        selected_question_ids: list[str] = [str(q.sheets_row_id) for q in selected_questions]

        logger.info(f"Selected {len(selected_question_ids)} assessment questions (all available)")

        return selected_question_ids

    def get_assessment_questions(
        self, db: Session, question_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Get assessment question data by sheets_row_ids.

        Args:
            db: Database session
            question_ids: List of question sheets_row_id strings

        Returns:
            List of question dictionaries with id (sheets_row_id), weight, correct_answer
        """
        questions = (
            db.query(AssessmentQuestion)
            .filter(AssessmentQuestion.sheets_row_id.in_(question_ids))
            .all()
        )

        return [
            {
                "id": q.sheets_row_id,
                "question_text": q.question_text,
                "answer_options": q.answer_options,
                "correct_answer": q.correct_answer,
                "weight": q.weight,
            }
            for q in questions
        ]

    async def complete_assessment(
        self,
        assessment_id: str,
        answers: dict[str, Any],
        score: float,
        level: str,
        db: Session,
    ) -> Assessment:
        """Complete an assessment with answers and determine level.

        Args:
            assessment_id: Assessment sheets_row_id.
            answers: Dictionary mapping question sheets_row_ids to user answers.
            score: Calculated score.
            level: Determined English level.
            db: Database session.

        Returns:
            Updated Assessment instance.
        """
        assessment = db.query(Assessment).filter(Assessment.sheets_row_id == assessment_id).first()
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
            assessment.user_id,
            assessment_id,
            score,
            level=level,
        )

        logger.info(
            "Assessment completed",
            extra={
                "assessment_id": assessment_id,
                "user_id": assessment.user_id,
                "score": score,
                "level": level,
            },
        )

        return assessment

    async def abandon_assessment(
        self,
        assessment_id: str,
        db: Session,
    ) -> Assessment:
        """Abandon an in-progress assessment.

        Args:
            assessment_id: Assessment sheets_row_id.
            db: Database session.

        Returns:
            Updated Assessment instance.
        """
        assessment = db.query(Assessment).filter(Assessment.sheets_row_id == assessment_id).first()
        if not assessment:
            raise AssessmentError(f"Assessment not found: {assessment_id}")

        assessment.status = AssessmentStatus.ABANDONED

        db.commit()
        db.refresh(assessment)

        logger.info(
            "Assessment abandoned",
            extra={
                "assessment_id": assessment_id,
                "user_id": assessment.user_id,
            },
        )

        return assessment
