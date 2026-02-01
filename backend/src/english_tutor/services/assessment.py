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


# CEFR levels in assessment order (easiest to hardest)
LEVELS_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


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

    # Early stop: offer to stop when user struggles (min answered, window size, thresholds)
    EARLY_STOP_MIN_ANSWERED = 12
    EARLY_STOP_WINDOW_SIZE = 6
    EARLY_STOP_MAX_CORRECT_IN_WINDOW = 2  # <= this many correct in last window → offer stop
    EARLY_STOP_CONSECUTIVE_WRONG = 4  # this many wrong in a row → offer stop

    def calculate_score(
        self,
        questions: list[dict[str, Any]],
        answers: dict[str, Any],
    ) -> float:
        """Calculate assessment score from correct answers.

        Args:
            questions: List of question dictionaries with id, correct_answer.
            answers: Dictionary mapping question IDs to user answers.

        Returns:
            Score as float between 0.0 and 1.0 (fraction of correct answers).
        """
        total = 0
        correct = 0

        for question in questions:
            question_id = question["id"]
            correct_answer = question["correct_answer"]

            if question_id in answers:
                total += 1
                if answers[question_id] == correct_answer:
                    correct += 1

        if total == 0:
            return 0.0

        return correct / total

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
        start_from_level: str | None = None,
    ) -> Assessment:
        """Start a new assessment for a user.

        Args:
            user_id: User telegram_user_id.
            db: Database session.
            question_ids: Optional list of question sheets_row_ids to use. If None, will be selected.
            sheets_row_id: Optional sheets_row_id for the assessment. If None, will be generated.
            start_from_level: Optional level (A1-C2) to start questions from. Used when user
                completed all tasks correctly and is re-assessing to advance (e.g. A1 user
                passes start_from_level='A2' to skip A1 questions).

        Returns:
            Created Assessment instance.
        """
        # Select questions if question_ids is None
        if question_ids is None:
            question_ids = self._select_assessment_questions(db, start_from_level=start_from_level)

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

    def _select_assessment_questions(
        self, db: Session, start_from_level: str | None = None
    ) -> list[str]:
        """Select assessment questions, ordered by level (A1–C2) then sheets_row_id.

        Content can grow or change at any time; no per-level or total limit is applied.
        For each level in order A1, A2, B1, B2, C1, C2, all questions for that level
        are included, ordered by sheets_row_id.

        Args:
            db: Database session
            start_from_level: If set (e.g. 'A2'), skip levels before this and start from
                this level. Used when user completed all tasks and is re-assessing to advance.

        Returns:
            List of question sheets_row_ids as strings, ordered by level then sheets_row_id
        """
        levels_to_include = LEVELS_ORDER
        if start_from_level and start_from_level in LEVELS_ORDER:
            start_idx = LEVELS_ORDER.index(start_from_level)
            levels_to_include = LEVELS_ORDER[start_idx:]
            logger.info(
                f"Starting assessment from level {start_from_level} (skipping earlier levels)"
            )

        selected_question_ids: list[str] = []
        for level in levels_to_include:
            level_questions = (
                db.query(AssessmentQuestion.sheets_row_id)
                .filter(
                    AssessmentQuestion.level == level,
                    AssessmentQuestion.sheets_row_id.isnot(None),
                )
                .order_by(AssessmentQuestion.sheets_row_id)
                .all()
            )
            selected_question_ids.extend(str(q.sheets_row_id) for q in level_questions)

        logger.info(
            f"Selected {len(selected_question_ids)} assessment questions "
            f"(levels: {levels_to_include})"
        )
        return selected_question_ids

    def should_offer_early_stop(
        self,
        questions: list[dict[str, Any]],
        answers: dict[str, Any],
        *,
        min_answered: int | None = None,
        window_size: int | None = None,
        max_correct_in_window: int | None = None,
        consecutive_wrong: int | None = None,
    ) -> bool:
        """Return True if user is struggling and we should offer to stop and assign current level.

        Uses two triggers (either is enough):
        - Last N consecutive answers are wrong.
        - In the last W answers, at most M are correct (low accuracy).

        Args:
            questions: List of question dicts with 'id' and 'correct_answer', in assessment order.
            answers: Dict mapping question id to user answer index.
            min_answered: Minimum number of answered questions before offering (default from config).
            window_size: Number of last answers to consider for accuracy (default from config).
            max_correct_in_window: Max correct in window to count as struggling (default from config).
            consecutive_wrong: Consecutive wrong answers to count as struggling (default from config).

        Returns:
            True if we should show "Continue or assign current level" prompt.
        """
        min_answered = min_answered if min_answered is not None else self.EARLY_STOP_MIN_ANSWERED
        window_size = window_size if window_size is not None else self.EARLY_STOP_WINDOW_SIZE
        max_correct_in_window = (
            max_correct_in_window
            if max_correct_in_window is not None
            else self.EARLY_STOP_MAX_CORRECT_IN_WINDOW
        )
        consecutive_wrong = (
            consecutive_wrong
            if consecutive_wrong is not None
            else self.EARLY_STOP_CONSECUTIVE_WRONG
        )

        # Build list of (question_id, correct_answer) in order
        ordered: list[tuple[str, int]] = [(q["id"], q["correct_answer"]) for q in questions]
        answered_correctness: list[bool] = []
        for qid, correct_idx in ordered:
            if qid not in answers:
                continue
            answered_correctness.append(answers[qid] == correct_idx)

        if len(answered_correctness) < min_answered:
            return False

        last_n = answered_correctness[-window_size:]
        correct_in_window = sum(1 for c in last_n if c)
        if correct_in_window <= max_correct_in_window:
            return True

        # Consecutive wrong at the end
        count_wrong = 0
        for c in reversed(answered_correctness):
            if c:
                break
            count_wrong += 1
        return count_wrong >= consecutive_wrong

    def get_assessment_questions(
        self, db: Session, question_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Get assessment question data by sheets_row_ids.

        Args:
            db: Database session
            question_ids: List of question sheets_row_id strings

        Returns:
            List of question dictionaries with id (sheets_row_id), correct_answer
        """
        questions = (
            db.query(AssessmentQuestion)
            .filter(AssessmentQuestion.sheets_row_id.in_(question_ids))
            .all()
        )
        by_id = {q.sheets_row_id: q for q in questions}
        # Preserve order of question_ids (assessment order)
        return [
            {
                "id": by_id[qid].sheets_row_id,
                "question_text": by_id[qid].question_text,
                "answer_options": by_id[qid].answer_options,
                "correct_answer": by_id[qid].correct_answer,
            }
            for qid in question_ids
            if qid in by_id
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
