"""Content synchronization service.

This module provides the main ContentSyncService that orchestrates syncing
content from Google Sheets/Drive to the database.
"""

from typing import Any, Optional

from sqlalchemy.orm import Session

from src.english_tutor.config import get_session_local
from src.english_tutor.services.content_sync.assessment_sync import AssessmentSyncService
from src.english_tutor.services.content_sync.base import SyncStats, log_sync
from src.english_tutor.services.content_sync.question_sync import QuestionSyncService
from src.english_tutor.services.content_sync.task_sync import TaskSyncService
from src.english_tutor.services.google_drive import GoogleDriveService
from src.english_tutor.services.google_sheets import GoogleSheetsService
from src.english_tutor.utils.exceptions import ContentManagementError
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)


class ContentSyncService:
    """Service for syncing content from Google Sheets/Drive to database.

    This service orchestrates the synchronization of tasks, questions, and
    assessment questions from Google Sheets to the PostgreSQL database.

    Attributes:
        sheets_service: Google Sheets service for reading data.
        drive_service: Google Drive service for resolving media URLs.
        task_sync: Service for syncing tasks.
        question_sync: Service for syncing questions.
        assessment_sync: Service for syncing assessment questions.

    Example:
        >>> service = ContentSyncService()
        >>> stats = service.sync_all(db)
        >>> print(f"Tasks created: {stats['tasks_created']}")
    """

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

        # Initialize sub-services
        self.task_sync = TaskSyncService(drive_service=self.drive_service)
        self.question_sync = QuestionSyncService()
        self.assessment_sync = AssessmentSyncService()

        logger.info("Content sync service initialized")

    def sync_all(self, db: Optional[Session] = None) -> SyncStats:
        """Sync all content from Google Sheets/Drive to database.

        Orchestrates the synchronization of tasks, questions, and assessment
        questions in the correct order (tasks first, then questions).

        Args:
            db: Database session. If None, creates new session.

        Returns:
            SyncStats with aggregated statistics:
            - tasks_created: Number of tasks created
            - tasks_updated: Number of tasks updated
            - tasks_deleted: Number of tasks deleted
            - tasks_skipped: Number of tasks skipped (no changes)
            - questions_created: Number of questions created
            - questions_updated: Number of questions updated
            - questions_deleted: Number of questions deleted
            - questions_skipped: Number of questions skipped (no changes)
            - assessment_questions_created: Number of assessment questions created
            - assessment_questions_updated: Number of assessment questions updated
            - assessment_questions_skipped: Number of assessment questions skipped
            - errors: Number of errors encountered

        Raises:
            ContentManagementError: If sync fails critically.

        Example:
            >>> service = ContentSyncService()
            >>> stats = service.sync_all(db)
            >>> print(f"Created {stats['tasks_created']} tasks")
        """
        stats: SyncStats = {
            "tasks_created": 0,
            "tasks_updated": 0,
            "tasks_deleted": 0,
            "tasks_skipped": 0,
            "questions_created": 0,
            "questions_updated": 0,
            "questions_deleted": 0,
            "questions_skipped": 0,
            "assessment_questions_created": 0,
            "assessment_questions_updated": 0,
            "assessment_questions_skipped": 0,
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

            # Read data from Google Sheets
            tasks_data, questions_data, assessment_questions_data = self._read_sheets_data()

            # Build mapping of task_row_id -> task data
            tasks_by_row_id = self._build_tasks_mapping(tasks_data)

            # Sync tasks first (questions depend on tasks)
            log_sync("Syncing tasks to database...")
            task_stats = self.task_sync.sync_tasks(db, tasks_by_row_id)
            self._merge_stats(stats, task_stats)
            log_sync(
                f"Tasks sync completed: {task_stats.get('tasks_created', 0)} created, "
                f"{task_stats.get('tasks_updated', 0)} updated, "
                f"{task_stats.get('tasks_skipped', 0)} skipped, "
                f"{task_stats.get('tasks_deleted', 0)} deleted"
            )

            # Sync questions (after tasks are synced)
            log_sync("Syncing questions to database...")
            question_stats = self.question_sync.sync_questions(db, questions_data, tasks_by_row_id)
            self._merge_stats(stats, question_stats)
            log_sync(
                f"Questions sync completed: {question_stats.get('questions_created', 0)} created, "
                f"{question_stats.get('questions_updated', 0)} updated, "
                f"{question_stats.get('questions_skipped', 0)} skipped, "
                f"{question_stats.get('questions_deleted', 0)} deleted"
            )

            # Sync assessment questions
            log_sync("Syncing assessment questions to database...")
            assessment_stats = self.assessment_sync.sync_assessment_questions(
                db, assessment_questions_data
            )
            self._merge_stats(stats, assessment_stats)
            log_sync(
                f"Assessment questions sync completed: "
                f"{assessment_stats.get('assessment_questions_created', 0)} created, "
                f"{assessment_stats.get('assessment_questions_updated', 0)} updated, "
                f"{assessment_stats.get('assessment_questions_skipped', 0)} skipped"
            )

            db.commit()
            log_sync(f"Content sync completed successfully: {stats}")

            return stats

        except Exception as e:
            db.rollback()
            logger.error("Content sync failed", extra={"error": str(e)}, exc_info=True)
            stats["errors"] = stats.get("errors", 0) + 1
            raise
        finally:
            if close_db:
                db.close()

    def _read_sheets_data(
        self,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """Read all data from Google Sheets.

        Returns:
            Tuple of (tasks_data, questions_data, assessment_questions_data).

        Raises:
            ContentManagementError: If reading from Sheets fails.
        """
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

            return tasks_data, questions_data, assessment_questions_data

        except Exception as e:
            logger.error(
                "Failed to read from Google Sheets",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise ContentManagementError(f"Failed to read from Google Sheets: {e}") from e

    def _build_tasks_mapping(self, tasks_data: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Build mapping of task row_id to task data.

        Args:
            tasks_data: List of task data dictionaries from Sheets.

        Returns:
            Dictionary mapping row_id to task data.
        """
        tasks_by_row_id: dict[str, dict[str, Any]] = {}

        for task_data in tasks_data:
            row_id = task_data.get("row_id")
            if row_id:
                tasks_by_row_id[row_id] = task_data

        log_sync(f"Built task mapping: {len(tasks_by_row_id)} tasks with row_ids")
        return tasks_by_row_id

    def _merge_stats(self, target: SyncStats, source: SyncStats) -> None:
        """Merge source stats into target stats.

        Args:
            target: Target stats dictionary to update.
            source: Source stats dictionary to merge from.
        """
        for key, value in source.items():
            if key in target and isinstance(value, int):
                target[key] = target.get(key, 0) + value
            elif key not in target and isinstance(value, int):
                target[key] = value
