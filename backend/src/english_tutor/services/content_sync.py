"""Content synchronization service.

This service syncs content from Google Sheets and Google Drive to PostgreSQL database.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.english_tutor.config import get_session_local
from src.english_tutor.models.question import Question
from src.english_tutor.models.task import Task, TaskStatus
from src.english_tutor.services.google_drive import GoogleDriveService
from src.english_tutor.services.google_sheets import GoogleSheetsService
from src.english_tutor.utils.exceptions import ContentManagementError
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)


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
            "errors": 0,
        }

        session_local = get_session_local()
        if db is None:
            db = session_local()
            close_db = True
        else:
            close_db = False

        try:
            logger.info("Starting content sync from Google Sheets/Drive")

            # Read tasks and questions from Sheets
            try:
                tasks_data = self.sheets_service.read_tasks()
                questions_data = self.sheets_service.read_questions()
            except Exception as e:
                logger.error(f"Failed to read from Google Sheets: {e}")
                stats["errors"] += 1
                raise ContentManagementError(f"Failed to read from Google Sheets: {e}") from e

            # Build mapping of task_row_id -> task data
            tasks_by_row_id: dict[str, dict[str, Any]] = {}
            for task_data in tasks_data:
                row_id = task_data.get("row_id")
                if row_id:
                    tasks_by_row_id[row_id] = task_data

            # Sync tasks
            task_stats = self._sync_tasks(db, tasks_by_row_id)
            stats.update(task_stats)

            # Sync questions (after tasks are synced)
            question_stats = self._sync_questions(db, questions_data, tasks_by_row_id)
            stats.update(question_stats)

            db.commit()
            logger.info(f"Content sync completed: {stats}")

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
            "tasks_deleted": 0,
        }

        # Get all existing tasks with row_id tracking
        # Note: We'll need to add a row_id column to Task model for tracking
        existing_row_ids = set()

        # Process each task from Sheets
        for row_id, task_data in tasks_by_row_id.items():
            try:
                # Resolve Drive file IDs to URLs if needed
                task_data = self._resolve_media_urls(task_data)

                # Find existing task by row_id (if we have that field)
                # For now, we'll match by title + level + type as fallback
                existing_task = self._find_task_by_row_id(db, row_id, task_data)

                if existing_task:
                    # Update existing task
                    self._update_task(existing_task, task_data, row_id)
                    stats["tasks_updated"] += 1
                    existing_row_ids.add(row_id)
                    logger.debug(f"Updated task: {task_data.get('title')}")
                else:
                    # Create new task
                    self._create_task(db, task_data, row_id)
                    stats["tasks_created"] += 1
                    existing_row_ids.add(row_id)
                    logger.debug(f"Created task: {task_data.get('title')}")

            except Exception as e:
                logger.error(f"Error syncing task {row_id}: {e}")
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
        for task_row_id, question_list in questions_by_task.items():
            try:
                # Find the task in database
                task = self._find_task_by_row_id(
                    db, task_row_id, tasks_by_row_id.get(task_row_id, {})
                )

                if not task:
                    logger.warning(f"Task with row_id {task_row_id} not found, skipping questions")
                    continue

                # Get existing questions for this task
                existing_questions = db.query(Question).filter(Question.task_id == task.id).all()
                existing_row_ids = {q.sheets_row_id for q in existing_questions if q.sheets_row_id}

                # Process each question
                for question_data in question_list:
                    row_id = question_data.get("row_id")
                    existing_question = None

                    # Find existing question by row_id
                    if row_id:
                        for q in existing_questions:
                            if q.sheets_row_id == row_id:
                                existing_question = q
                                break

                    if existing_question:
                        # Update existing question
                        self._update_question(existing_question, question_data, row_id)
                        stats["questions_updated"] += 1
                        existing_row_ids.discard(row_id)
                    else:
                        # Create new question
                        self._create_question(db, task.id, question_data, row_id)
                        stats["questions_created"] += 1

                # Delete questions not in Sheets (optional - be careful with this)
                # For now, we'll leave orphaned questions

            except Exception as e:
                logger.error(f"Error syncing questions for task {task_row_id}: {e}")
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

        if task_type == "audio":
            drive_id = task_data.get("content_audio_drive_id")
            if drive_id:
                try:
                    url = self.drive_service.get_file_download_url(drive_id)
                    task_data["content_audio_url"] = url
                    # Remove drive_id key
                    task_data.pop("content_audio_drive_id", None)
                except Exception as e:
                    logger.error(f"Failed to resolve audio file {drive_id}: {e}")
                    # Keep drive_id, sync will fail validation

        elif task_type == "video":
            drive_id = task_data.get("content_video_drive_id")
            if drive_id:
                try:
                    url = self.drive_service.get_file_download_url(drive_id)
                    task_data["content_video_url"] = url
                    # Remove drive_id key
                    task_data.pop("content_video_drive_id", None)
                except Exception as e:
                    logger.error(f"Failed to resolve video file {drive_id}: {e}")
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
            content_text=task_data.get("content_text"),
            content_audio_url=task_data.get("content_audio_url"),
            content_video_url=task_data.get("content_video_url"),
            explanation=task_data.get("explanation"),
            difficulty=task_data.get("difficulty"),
            status=TaskStatus(task_data.get("status", "draft")),
            sheets_row_id=row_id,
        )
        db.add(task)
        db.flush()  # Get the ID
        return task

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
        task.content_text = task_data.get("content_text")
        task.content_audio_url = task_data.get("content_audio_url")
        task.content_video_url = task_data.get("content_video_url")
        task.explanation = task_data.get("explanation")
        task.difficulty = task_data.get("difficulty")
        task.status = TaskStatus(task_data.get("status", "draft"))
        task.sheets_row_id = row_id
        task.updated_at = datetime.utcnow()

    def _create_question(
        self,
        db: Session,
        task_id: UUID,
        question_data: dict[str, Any],
        row_id: str,
    ) -> Question:
        """Create a new question in database.

        Args:
            db: Database session
            task_id: Parent task ID
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
            order=question_data["order"],
            sheets_row_id=row_id,
        )
        db.add(question)
        db.flush()
        return question

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
        question.order = question_data["order"]
        question.sheets_row_id = row_id
        question.updated_at = datetime.utcnow()
