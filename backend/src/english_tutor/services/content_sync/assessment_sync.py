"""Assessment question synchronization service.

Service for syncing assessment questions from Google Sheets to the database.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.english_tutor.models.assessment_question import AssessmentQuestion
from src.english_tutor.services.content_sync.base import SyncStats, log_sync
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)


class AssessmentSyncService:
    """Service for syncing assessment questions from Google Sheets to database.

    This service handles the synchronization of assessment question data from
    Google Sheets, which is used for determining user proficiency levels.

    Example:
        >>> service = AssessmentSyncService()
        >>> stats = service.sync_assessment_questions(db, questions_data)
        >>> print(f"Created: {stats['assessment_questions_created']}")
    """

    def sync_assessment_questions(
        self,
        db: Session,
        assessment_questions_data: list[dict[str, Any]],
    ) -> SyncStats:
        """Sync assessment questions from Google Sheets to database.

        Processes each assessment question from the sheets data, creating new
        questions or updating existing ones. Questions are matched by their
        sheets_row_id.

        Args:
            db: Database session for persistence operations.
            assessment_questions_data: List of assessment question data from Sheets.

        Returns:
            SyncStats with counts of created, updated, skipped assessment questions.

        Example:
            >>> service = AssessmentSyncService()
            >>> stats = service.sync_assessment_questions(db, [{"row_id": "q1", ...}])
            >>> print(f"Created: {stats['assessment_questions_created']}")
        """
        stats: SyncStats = {
            "tasks_created": 0,
            "tasks_updated": 0,
            "tasks_skipped": 0,
            "tasks_deleted": 0,
            "questions_created": 0,
            "questions_updated": 0,
            "questions_skipped": 0,
            "questions_deleted": 0,
            "assessment_questions_created": 0,
            "assessment_questions_updated": 0,
            "assessment_questions_skipped": 0,
            "errors": 0,
        }

        total_questions = len(assessment_questions_data)
        log_sync(f"Processing {total_questions} assessment questions")

        for idx, question_data in enumerate(assessment_questions_data, 1):
            try:
                row_id = question_data.get("row_id")
                if not row_id:
                    logger.warning(
                        "Skipping assessment question: missing row_id",
                        extra={"index": idx, "total": total_questions},
                    )
                    continue

                log_sync(f"Processing assessment [{idx}/{total_questions}]: {row_id}")

                existing_question = self._find_by_row_id(db, row_id)

                if existing_question:
                    if self._has_changed(existing_question, question_data):
                        self._update_question(existing_question, question_data, row_id)
                        stats["assessment_questions_updated"] += 1
                        log_sync(f"Updated assessment: {row_id}")
                    else:
                        stats["assessment_questions_skipped"] += 1
                        log_sync(f"Skipped assessment: {row_id} (no changes)")
                else:
                    self._create_question(db, question_data, row_id)
                    stats["assessment_questions_created"] += 1
                    log_sync(f"Created assessment: {row_id}")

            except Exception as e:
                row_id = question_data.get("row_id", "unknown")
                logger.error(
                    "Error syncing assessment question",
                    extra={"row_id": row_id, "error": str(e)},
                    exc_info=True,
                )
                log_sync(f"Error assessment: {row_id} - {e}", level="error")
                stats["errors"] = stats.get("errors", 0) + 1

        return stats

    def _find_by_row_id(
        self,
        db: Session,
        row_id: str,
    ) -> AssessmentQuestion | None:
        """Find assessment question in database by row_id.

        Args:
            db: Database session.
            row_id: Google Sheets row ID.

        Returns:
            AssessmentQuestion instance if found, None otherwise.
        """
        return (
            db.query(AssessmentQuestion).filter(AssessmentQuestion.sheets_row_id == row_id).first()
        )

    def _create_question(
        self,
        db: Session,
        question_data: dict[str, Any],
        row_id: str,
    ) -> AssessmentQuestion:
        """Create a new assessment question in the database.

        Args:
            db: Database session.
            question_data: Assessment question data from Sheets.
            row_id: Google Sheets row ID for tracking.

        Returns:
            Created AssessmentQuestion instance.
        """
        question = AssessmentQuestion(
            sheets_row_id=row_id,
            level=question_data["level"],
            question_text=question_data["question_text"],
            answer_options=question_data["answer_options"],
            correct_answer=question_data["correct_answer"],
        )
        db.add(question)
        db.flush()

        logger.info(
            "Created new assessment question",
            extra={"row_id": row_id, "level": question_data["level"]},
        )

        return question

    def _has_changed(
        self,
        question: AssessmentQuestion,
        question_data: dict[str, Any],
    ) -> bool:
        """Check if assessment question data has changed compared to database.

        Compares all significant fields to determine if an update is needed.

        Args:
            question: Existing AssessmentQuestion instance from database.
            question_data: Assessment question data from Sheets.

        Returns:
            True if any field has changed, False otherwise.
        """
        if question.level != question_data["level"]:
            return True
        if question.question_text != question_data["question_text"]:
            return True
        if question.answer_options != question_data["answer_options"]:
            return True
        if question.correct_answer != question_data["correct_answer"]:
            return True

        return False

    def _update_question(
        self,
        question: AssessmentQuestion,
        question_data: dict[str, Any],
        row_id: str,
    ) -> None:
        """Update existing assessment question with data from Sheets.

        Args:
            question: Existing AssessmentQuestion instance to update.
            question_data: Assessment question data from Sheets.
            row_id: Google Sheets row ID.
        """
        question.level = question_data["level"]
        question.question_text = question_data["question_text"]
        question.answer_options = question_data["answer_options"]
        question.correct_answer = question_data["correct_answer"]
        question.sheets_row_id = row_id
        question.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        logger.info(
            "Updated assessment question",
            extra={"row_id": row_id, "level": question_data["level"]},
        )
