"""Content synchronization service.

This service syncs content from Google Sheets and Google Drive to PostgreSQL database.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.english_tutor.config import get_session_local
from src.english_tutor.models.assessment_question import AssessmentQuestion
from src.english_tutor.models.question import Question
from src.english_tutor.models.task import Task, TaskStatus
from src.english_tutor.services.google_drive import GoogleDriveService
from src.english_tutor.services.google_sheets import GoogleSheetsService
from src.english_tutor.utils.exceptions import ContentManagementError
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)

# Ensure the logger propagates to root logger and is set to INFO level
logger.setLevel(logging.INFO)
logger.propagate = True  # Ensure logs propagate to root logger


# Helper function to both log and print for visibility
def log_sync(message: str, level: str = "info") -> None:
    """Log message and also print to stderr for immediate visibility."""
    import sys

    getattr(logger, level.lower())(message)
    print(f"[SYNC {level.upper()}] {message}", file=sys.stderr)
    sys.stderr.flush()


class ContentSyncService:
    """Service for syncing content from Google Sheets/Drive to database."""

    def __init__(
        self,
        sheets_service: Optional[GoogleSheetsService] = None,
        drive_service: Optional[GoogleDriveService] = None,
    ) -> None:
        """Initialize content sync service.

        Args:
            sheets_service: Google Sheets service instance. If None, creates new instance.
            drive_service: Google Drive service instance. If None, creates new instance.
        """
        self.sheets_service = sheets_service or GoogleSheetsService()
        self.drive_service = drive_service or GoogleDriveService()
        logger.info("Content sync service initialized")

    def sync_all(self, db: Optional[Session] = None) -> dict[str, int]:
        """Sync all content from Google Sheets/Drive to database.

        Args:
            db: Database session. If None, creates new session.

        Returns:
            Dictionary with sync statistics:
            - tasks_created: Number of tasks created
            - tasks_updated: Number of tasks updated
            - tasks_deleted: Number of tasks deleted
            - questions_created: Number of questions created
            - questions_updated: Number of questions updated
            - questions_deleted: Number of questions deleted
            - assessment_questions_created: Number of assessment questions created
            - assessment_questions_updated: Number of assessment questions updated
            - errors: Number of errors encountered

        Raises:
            ContentManagementError: If sync fails critically
        """
        stats = {
            "tasks_created": 0,
            "tasks_updated": 0,
            "tasks_deleted": 0,
            "questions_created": 0,
            "questions_updated": 0,
            "questions_deleted": 0,
            "assessment_questions_created": 0,
            "assessment_questions_updated": 0,
            "errors": 0,
        }

        session_local = get_session_local()
        if db is None:
            db = session_local()
            close_db = True
        else:
            close_db = False

        try:
            log_sync("=" * 80)
            log_sync("Starting content sync from Google Sheets/Drive")
            log_sync("=" * 80)

            # Read tasks, questions, and assessment questions from Sheets
            try:
                log_sync("Reading tasks from Google Sheets...")
                tasks_data = self.sheets_service.read_tasks()
                log_sync(f"Read {len(tasks_data)} tasks from Google Sheets")

                log_sync("Reading questions from Google Sheets...")
                questions_data = self.sheets_service.read_questions()
                log_sync(f"Read {len(questions_data)} questions from Google Sheets")

                log_sync("Reading assessment questions from Google Sheets...")
                assessment_questions_data = self.sheets_service.read_assessment_questions()
                log_sync(
                    f"Read {len(assessment_questions_data)} assessment questions from Google Sheets"
                )
            except Exception as e:
                logger.error(f"Failed to read from Google Sheets: {e}", exc_info=True)
                stats["errors"] += 1
                raise ContentManagementError(f"Failed to read from Google Sheets: {e}") from e

            # Build mapping of task_row_id -> task data
            tasks_by_row_id: dict[str, dict[str, Any]] = {}
            for task_data in tasks_data:
                row_id = task_data.get("row_id")
                if row_id:
                    tasks_by_row_id[row_id] = task_data
            log_sync(f"Built task mapping: {len(tasks_by_row_id)} tasks with row_ids")

            # Sync tasks
            log_sync("Syncing tasks to database...")
            task_stats = self._sync_tasks(db, tasks_by_row_id)
            stats.update(task_stats)
            log_sync(
                f"Tasks sync completed: {task_stats['tasks_created']} created, "
                f"{task_stats['tasks_updated']} updated, "
                f"{task_stats.get('tasks_skipped', 0)} skipped (no changes), "
                f"{task_stats['tasks_deleted']} deleted"
            )

            # Sync questions (after tasks are synced)
            log_sync("Syncing questions to database...")
            question_stats = self._sync_questions(db, questions_data, tasks_by_row_id)
            stats.update(question_stats)
            log_sync(
                f"Questions sync completed: {question_stats['questions_created']} created, "
                f"{question_stats['questions_updated']} updated, "
                f"{question_stats.get('questions_skipped', 0)} skipped (no changes), "
                f"{question_stats['questions_deleted']} deleted"
            )

            # Sync assessment questions
            log_sync("Syncing assessment questions to database...")
            assessment_question_stats = self._sync_assessment_questions(
                db, assessment_questions_data
            )
            stats.update(assessment_question_stats)
            log_sync(
                f"Assessment questions sync completed: "
                f"{assessment_question_stats['assessment_questions_created']} created, "
                f"{assessment_question_stats['assessment_questions_updated']} updated, "
                f"{assessment_question_stats.get('assessment_questions_skipped', 0)} skipped (no changes)"
            )

            db.commit()
            log_sync(f"Content sync completed successfully: {stats}")

            return stats

        except Exception as e:
            db.rollback()
            logger.error(f"Content sync failed: {e}")
            stats["errors"] += 1
            raise
        finally:
            if close_db:
                db.close()

    def _sync_tasks(
        self,
        db: Session,
        tasks_by_row_id: dict[str, dict[str, Any]],
    ) -> dict[str, int]:
        """Sync tasks from Google Sheets to database.

        Args:
            db: Database session
            tasks_by_row_id: Dictionary mapping row_id to task data

        Returns:
            Statistics dictionary
        """
        stats = {
            "tasks_created": 0,
            "tasks_updated": 0,
            "tasks_skipped": 0,
            "tasks_deleted": 0,
        }

        # Get all existing tasks with row_id tracking
        # Note: We'll need to add a row_id column to Task model for tracking
        existing_row_ids = set()
        total_tasks = len(tasks_by_row_id)
        log_sync(f"Processing {total_tasks} tasks from Google Sheets")

        # Process each task from Sheets
        for idx, (row_id, task_data) in enumerate(tasks_by_row_id.items(), 1):
            try:
                log_sync(f"Processing task [{idx}/{total_tasks}]: {row_id}")

                # Resolve Drive file IDs to URLs if needed
                if task_data.get("type") in ("audio", "video"):
                    drive_id = (
                        task_data.get("content_audio_drive_id")
                        or task_data.get("content_video_drive_id")
                        or task_data.get("content_drive_id")
                    )
                    if drive_id:
                        logger.info(f"Resolving media URL for task {row_id} (drive_id={drive_id})")
                task_data = self._resolve_media_urls(task_data)

                # Find existing task by row_id (if we have that field)
                # For now, we'll match by title + level + type as fallback
                existing_task = self._find_task_by_row_id(db, row_id, task_data)

                if existing_task:
                    # Check if data has changed before updating
                    if self._has_task_changed(existing_task, task_data):
                        self._update_task(existing_task, task_data, row_id)
                        stats["tasks_updated"] += 1
                        log_sync(f"✓ Updated task: {row_id}")
                    else:
                        stats["tasks_skipped"] += 1
                        log_sync(f"⊘ Skipped task: {row_id} (no changes)")
                    existing_row_ids.add(row_id)
                else:
                    # Create new task
                    self._create_task(db, task_data, row_id)
                    stats["tasks_created"] += 1
                    existing_row_ids.add(row_id)
                    log_sync(f"✓ Created task: {row_id}")

            except Exception as e:
                error_msg = f"✗ Error syncing task {row_id}: {e}"
                logger.error(error_msg, exc_info=True)
                log_sync(f"✗ Error task: {row_id} - {e}", level="error")
                stats.setdefault("errors", 0)
                stats["errors"] += 1
                continue

        # Mark tasks not in Sheets as deleted (or draft)
        # For safety, we might want to only delete if explicitly marked
        # For now, we'll leave orphaned tasks alone

        return stats

    def _sync_questions(
        self,
        db: Session,
        questions_data: list[dict[str, Any]],
        tasks_by_row_id: dict[str, dict[str, Any]],
    ) -> dict[str, int]:
        """Sync questions from Google Sheets to database.

        Args:
            db: Database session
            questions_data: List of question data from Sheets
            tasks_by_row_id: Dictionary mapping task row_id to task data

        Returns:
            Statistics dictionary
        """
        stats = {
            "questions_created": 0,
            "questions_updated": 0,
            "questions_skipped": 0,
            "questions_deleted": 0,
        }

        # Group questions by task_row_id
        questions_by_task: dict[str, list[dict[str, Any]]] = {}
        for question_data in questions_data:
            task_row_id = question_data.get("task_row_id")
            if task_row_id:
                if task_row_id not in questions_by_task:
                    questions_by_task[task_row_id] = []
                questions_by_task[task_row_id].append(question_data)

        # Sync questions for each task
        for task_idx, (task_row_id, question_list) in enumerate(questions_by_task.items(), 1):
            try:
                task_info = tasks_by_row_id.get(task_row_id, {})

                # Find the task in database
                task = self._find_task_by_row_id(db, task_row_id, task_info)

                if not task:
                    logger.warning(
                        f"Task with row_id {task_row_id} not found in database, "
                        f"skipping {len(question_list)} questions"
                    )
                    continue

                # Get existing questions for this task
                existing_questions = (
                    db.query(Question).filter(Question.task_id == task.sheets_row_id).all()
                )
                existing_row_ids = {q.sheets_row_id for q in existing_questions if q.sheets_row_id}

                # Process each question
                for q_idx, question_data in enumerate(question_list, 1):
                    row_id = question_data.get("row_id")
                    if not row_id:
                        continue

                    log_sync(f"Processing questions [{q_idx}/{len(question_list)}]: {row_id}")

                    existing_question = None

                    # Find existing question by row_id
                    for q in existing_questions:
                        if q.sheets_row_id == row_id:
                            existing_question = q
                            break

                    if existing_question:
                        # Check if data has changed before updating
                        if self._has_question_changed(existing_question, question_data):
                            self._update_question(existing_question, question_data, row_id)
                            stats["questions_updated"] += 1
                            log_sync(f"  ✓ Updated question: {row_id}")
                        else:
                            stats["questions_skipped"] += 1
                            log_sync(f"  ⊘ Skipped question: {row_id} (no changes)")
                        existing_row_ids.discard(row_id)
                    else:
                        # Create new question
                        self._create_question(db, task.sheets_row_id, question_data, row_id)
                        stats["questions_created"] += 1
                        log_sync(f"  ✓ Created question: {row_id}")

                # Delete questions not in Sheets (optional - be careful with this)
                # For now, we'll leave orphaned questions
                if existing_row_ids:
                    logger.info(
                        f"  Note: {len(existing_row_ids)} questions in DB not found in Sheets "
                        f"(keeping them as-is)"
                    )

            except Exception as e:
                error_msg = f"Error syncing questions for task {task_row_id}: {e}"
                logger.error(error_msg, exc_info=True)
                log_sync(f"✗ Error questions for task {task_row_id}: {e}", level="error")
                continue

        return stats

    def _resolve_media_urls(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Resolve Google Drive file IDs to URLs.

        Args:
            task_data: Task data dictionary

        Returns:
            Updated task data with URLs instead of Drive IDs
        """
        task_type = task_data.get("type")

        if task_type in ("audio", "video"):
            # Try both possible field names for backward compatibility
            drive_id = (
                task_data.get("content_audio_drive_id")
                or task_data.get("content_video_drive_id")
                or task_data.get("content_drive_id")
            )
            if drive_id:
                try:
                    logger.debug(f"Resolving Google Drive file ID to URL: {drive_id}")
                    url = self.drive_service.get_file_download_url(drive_id)
                    task_data["content_url"] = url
                    logger.debug(f"Successfully resolved drive_id {drive_id} to URL: {url[:50]}...")
                    # Remove drive_id keys
                    task_data.pop("content_audio_drive_id", None)
                    task_data.pop("content_video_drive_id", None)
                    task_data.pop("content_drive_id", None)
                except Exception as e:
                    logger.error(
                        f"Failed to resolve media file {drive_id} for task "
                        f"{task_data.get('title', 'Unknown')}: {e}",
                        exc_info=True,
                    )
                    # Keep drive_id, sync will fail validation

        return task_data

    def _find_task_by_row_id(
        self,
        db: Session,
        row_id: str,
        task_data: dict[str, Any],
    ) -> Optional[Task]:
        """Find task in database by row_id or by matching fields.

        Args:
            db: Database session
            row_id: Google Sheets row ID
            task_data: Task data from Sheets

        Returns:
            Task instance or None
        """
        # First try to find by row_id
        if row_id:
            task = db.query(Task).filter(Task.sheets_row_id == row_id).first()
            if task:
                return task

        # Fallback: match by title + level + type
        title = task_data.get("title")
        level = task_data.get("level")
        task_type = task_data.get("type")

        if title and level and task_type:
            task = (
                db.query(Task)
                .filter(
                    and_(
                        Task.title == title,
                        Task.level == level,
                        Task.type == task_type,
                    )
                )
                .first()
            )
            return task

        return None

    def _create_task(self, db: Session, task_data: dict[str, Any], row_id: str) -> Task:
        """Create a new task in database.

        Args:
            db: Database session
            task_data: Task data from Sheets
            row_id: Google Sheets row ID

        Returns:
            Created Task instance
        """
        task = Task(
            level=task_data["level"],
            type=task_data["type"],
            title=task_data["title"],
            language_domain=task_data.get("language_domain"),
            content_text=task_data.get("content_text"),
            content_url=task_data.get("content_url"),
            explanation=task_data.get("explanation"),
            status=TaskStatus(task_data.get("status", "draft")),
            sheets_row_id=row_id,
        )
        db.add(task)
        db.flush()
        return task

    def _has_task_changed(self, task: Task, task_data: dict[str, Any]) -> bool:
        """Check if task data has changed.

        Args:
            task: Existing Task instance
            task_data: Task data from Sheets

        Returns:
            True if data has changed, False otherwise
        """
        if task.level != task_data["level"]:
            return True
        if task.type != task_data["type"]:
            return True
        if task.title != task_data["title"]:
            return True
        if task.language_domain != task_data.get("language_domain"):
            return True
        if task.content_text != task_data.get("content_text"):
            return True
        if task.content_url != task_data.get("content_url"):
            return True
        if task.explanation != task_data.get("explanation"):
            return True
        if task.status != TaskStatus(task_data.get("status", "draft")):
            return True
        return False

    def _update_task(self, task: Task, task_data: dict[str, Any], row_id: str) -> None:
        """Update existing task with data from Sheets.

        Args:
            task: Existing Task instance
            task_data: Task data from Sheets
            row_id: Google Sheets row ID
        """
        task.level = task_data["level"]
        task.type = task_data["type"]
        task.title = task_data["title"]
        task.language_domain = task_data.get("language_domain")
        task.content_text = task_data.get("content_text")
        task.content_url = task_data.get("content_url")
        task.explanation = task_data.get("explanation")
        task.status = TaskStatus(task_data.get("status", "draft"))
        task.sheets_row_id = row_id
        task.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def _create_question(
        self,
        db: Session,
        task_id: str,
        question_data: dict[str, Any],
        row_id: str,
    ) -> Question:
        """Create a new question in database.

        Args:
            db: Database session
            task_id: Parent task sheets_row_id
            question_data: Question data from Sheets
            row_id: Google Sheets row ID

        Returns:
            Created Question instance
        """
        question = Question(
            task_id=task_id,
            question_text=question_data["question_text"],
            answer_options=question_data["answer_options"],
            correct_answer=question_data["correct_answer"],
            weight=question_data.get("weight", 1.0),
            sheets_row_id=row_id,
        )
        db.add(question)
        db.flush()
        return question

    def _has_question_changed(self, question: Question, question_data: dict[str, Any]) -> bool:
        """Check if question data has changed.

        Args:
            question: Existing Question instance
            question_data: Question data from Sheets

        Returns:
            True if data has changed, False otherwise
        """
        # Compare JSONB fields - answer_options is stored as JSONB
        if question.answer_options != question_data["answer_options"]:
            return True
        if question.question_text != question_data["question_text"]:
            return True
        if question.correct_answer != question_data["correct_answer"]:
            return True
        # Float comparison with tolerance
        if abs(question.weight - question_data.get("weight", 1.0)) > 0.0001:
            return True
        return False

    def _update_question(
        self, question: Question, question_data: dict[str, Any], row_id: str
    ) -> None:
        """Update existing question with data from Sheets.

        Args:
            question: Existing Question instance
            question_data: Question data from Sheets
            row_id: Google Sheets row ID
        """
        question.question_text = question_data["question_text"]
        question.answer_options = question_data["answer_options"]
        question.correct_answer = question_data["correct_answer"]
        question.weight = question_data.get("weight", 1.0)
        question.sheets_row_id = row_id
        question.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def _sync_assessment_questions(
        self,
        db: Session,
        assessment_questions_data: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Sync assessment questions from Google Sheets to database.

        Args:
            db: Database session
            assessment_questions_data: List of assessment question data from Sheets

        Returns:
            Statistics dictionary
        """
        stats = {
            "assessment_questions_created": 0,
            "assessment_questions_updated": 0,
            "assessment_questions_skipped": 0,
        }

        total_questions = len(assessment_questions_data)

        # Process each assessment question from Sheets
        for idx, question_data in enumerate(assessment_questions_data, 1):
            try:
                row_id = question_data.get("row_id")
                if not row_id:
                    logger.warning(
                        f"Skipping assessment question [{idx}/{total_questions}]: missing row_id"
                    )
                    continue

                log_sync(f"Processing assessment [{idx}/{total_questions}]: {row_id}")

                # Find existing question by row_id
                existing_question = (
                    db.query(AssessmentQuestion)
                    .filter(AssessmentQuestion.sheets_row_id == row_id)
                    .first()
                )

                if existing_question:
                    # Check if data has changed before updating
                    if self._has_assessment_question_changed(existing_question, question_data):
                        self._update_assessment_question(existing_question, question_data, row_id)
                        stats["assessment_questions_updated"] += 1
                        log_sync(f"  ✓ Updated assessment: {row_id}")
                    else:
                        stats["assessment_questions_skipped"] += 1
                        log_sync(f"  ⊘ Skipped assessment: {row_id} (no changes)")
                else:
                    # Create new question
                    self._create_assessment_question(db, question_data, row_id)
                    stats["assessment_questions_created"] += 1
                    log_sync(f"  ✓ Created assessment: {row_id}")

            except Exception as e:
                row_id = question_data.get("row_id", "unknown")
                error_msg = f"✗ Error syncing assessment question {row_id}: {e}"
                logger.error(error_msg, exc_info=True)
                log_sync(f"✗ Error assessment: {row_id} - {e}", level="error")
                continue

        return stats

    def _create_assessment_question(
        self,
        db: Session,
        question_data: dict[str, Any],
        row_id: str,
    ) -> AssessmentQuestion:
        """Create a new assessment question in database.

        Args:
            db: Database session
            question_data: Assessment question data from Sheets
            row_id: Google Sheets row ID

        Returns:
            Created AssessmentQuestion instance
        """
        question = AssessmentQuestion(
            level=question_data["level"],
            question_text=question_data["question_text"],
            answer_options=question_data["answer_options"],
            correct_answer=question_data["correct_answer"],
            weight=question_data.get("weight", 1.0),
            sheets_row_id=row_id,
        )
        db.add(question)
        db.flush()
        return question

    def _has_assessment_question_changed(
        self,
        question: AssessmentQuestion,
        question_data: dict[str, Any],
    ) -> bool:
        """Check if assessment question data has changed.

        Args:
            question: Existing AssessmentQuestion instance
            question_data: Assessment question data from Sheets

        Returns:
            True if data has changed, False otherwise
        """
        # Compare JSONB fields - answer_options is stored as JSONB, should be list/dict
        existing_options = question.answer_options
        new_options = question_data["answer_options"]
        # JSONB from DB might be list or dict, ensure both are lists for comparison
        if existing_options != new_options:
            return True

        # Compare other fields
        if question.level != question_data["level"]:
            return True
        if question.question_text != question_data["question_text"]:
            return True
        if question.correct_answer != question_data["correct_answer"]:
            return True
        # Float comparison with tolerance
        if abs(question.weight - question_data.get("weight", 1.0)) > 0.0001:
            return True

        return False

    def _update_assessment_question(
        self,
        question: AssessmentQuestion,
        question_data: dict[str, Any],
        row_id: str,
    ) -> None:
        """Update existing assessment question with data from Sheets.

        Args:
            question: Existing AssessmentQuestion instance
            question_data: Assessment question data from Sheets
            row_id: Google Sheets row ID
        """
        question.level = question_data["level"]
        question.question_text = question_data["question_text"]
        question.answer_options = question_data["answer_options"]
        question.correct_answer = question_data["correct_answer"]
        question.weight = question_data.get("weight", 1.0)
        question.sheets_row_id = row_id
        question.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
