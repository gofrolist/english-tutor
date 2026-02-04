"""Task synchronization service.

Service for syncing tasks from Google Sheets/Drive to the database.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.english_tutor.models.task import Task, TaskStatus
from src.english_tutor.services.content_sync.base import SyncStats, log_sync
from src.english_tutor.services.google_drive import GoogleDriveService
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)


class TaskSyncService:
    """Service for syncing tasks from Google Sheets to database.

    This service handles the synchronization of task data from Google Sheets,
    including resolving media URLs from Google Drive for audio/video tasks.

    Attributes:
        drive_service: Google Drive service for resolving media URLs.
    """

    def __init__(self, drive_service: Optional[GoogleDriveService] = None) -> None:
        """Initialize task sync service.

        Args:
            drive_service: Google Drive service instance. If None, creates new instance.
        """
        self.drive_service = drive_service

    def sync_tasks(
        self,
        db: Session,
        tasks_by_row_id: dict[str, dict[str, Any]],
    ) -> SyncStats:
        """Sync tasks from Google Sheets to database.

        Processes each task from the sheets data, creating new tasks or updating
        existing ones. Tasks are matched by their sheets_row_id.

        Args:
            db: Database session for persistence operations.
            tasks_by_row_id: Dictionary mapping row_id to task data from Sheets.

        Returns:
            SyncStats with counts of created, updated, skipped, and deleted tasks.

        Example:
            >>> service = TaskSyncService(drive_service)
            >>> stats = service.sync_tasks(db, {"row_1": {"title": "Task 1", ...}})
            >>> print(f"Created: {stats['tasks_created']}")
        """
        stats: SyncStats = {
            "tasks_created": 0,
            "tasks_updated": 0,
            "tasks_skipped": 0,
            "tasks_deleted": 0,
            "errors": 0,
        }

        total_tasks = len(tasks_by_row_id)
        log_sync(f"Processing {total_tasks} tasks from Google Sheets")

        for idx, (row_id, task_data) in enumerate(tasks_by_row_id.items(), 1):
            try:
                log_sync(f"Processing task [{idx}/{total_tasks}]: {row_id}")

                # Resolve Drive file IDs to URLs for media tasks
                if task_data.get("type") in ("audio", "video"):
                    drive_id = self._get_drive_id(task_data)
                    if drive_id:
                        logger.info(
                            "Resolving media URL for task",
                            extra={"row_id": row_id, "drive_id": drive_id},
                        )
                task_data = self._resolve_media_urls(task_data)

                # Find existing task by row_id
                existing_task = self._find_task_by_row_id(db, row_id, task_data)

                if existing_task:
                    if self._has_task_changed(existing_task, task_data):
                        self._update_task(existing_task, task_data, row_id)
                        stats["tasks_updated"] += 1
                        log_sync(f"Updated task: {row_id}")
                    else:
                        stats["tasks_skipped"] += 1
                        log_sync(f"Skipped task: {row_id} (no changes)")
                else:
                    self._create_task(db, task_data, row_id)
                    stats["tasks_created"] += 1
                    log_sync(f"Created task: {row_id}")

            except Exception as e:
                logger.error(
                    "Error syncing task",
                    extra={"row_id": row_id, "error": str(e)},
                    exc_info=True,
                )
                log_sync(f"Error task: {row_id} - {e}", level="error")
                stats["errors"] = stats.get("errors", 0) + 1

        return stats

    def _get_drive_id(self, task_data: dict[str, Any]) -> Optional[str]:
        """Extract Google Drive file ID from task data.

        Args:
            task_data: Task data dictionary from Sheets.

        Returns:
            Drive file ID if found, None otherwise.
        """
        return (
            task_data.get("content_audio_drive_id")
            or task_data.get("content_video_drive_id")
            or task_data.get("content_drive_id")
        )

    def _resolve_media_urls(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Resolve Google Drive file IDs to downloadable URLs.

        For audio/video tasks, converts Drive file IDs to URLs that can be
        used by the Telegram bot to send media.

        Args:
            task_data: Task data dictionary from Sheets.

        Returns:
            Updated task data with content_url instead of Drive IDs.
        """
        task_type = task_data.get("type")

        if task_type not in ("audio", "video"):
            return task_data

        drive_id = self._get_drive_id(task_data)
        if not drive_id:
            return task_data

        if not self.drive_service:
            logger.warning(
                "Drive service not available, cannot resolve media URL",
                extra={"drive_id": drive_id},
            )
            return task_data

        try:
            logger.debug(
                "Resolving Google Drive file ID to URL",
                extra={"drive_id": drive_id},
            )
            url = self.drive_service.get_file_download_url(drive_id)
            task_data["content_url"] = url
            logger.debug(
                "Successfully resolved drive_id to URL",
                extra={"drive_id": drive_id, "url": url[:50] + "..."},
            )
            # Remove drive_id keys after resolution
            task_data.pop("content_audio_drive_id", None)
            task_data.pop("content_video_drive_id", None)
            task_data.pop("content_drive_id", None)
        except Exception as e:
            logger.error(
                "Failed to resolve media file URL",
                extra={
                    "drive_id": drive_id,
                    "task_title": task_data.get("title", "Unknown"),
                    "error": str(e),
                },
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

        First attempts to find by sheets_row_id. Falls back to matching
        by title + level + type for tasks created before row_id tracking.

        Args:
            db: Database session.
            row_id: Google Sheets row ID.
            task_data: Task data from Sheets for fallback matching.

        Returns:
            Task instance if found, None otherwise.
        """
        # Primary lookup by row_id
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

    def _create_task(
        self,
        db: Session,
        task_data: dict[str, Any],
        row_id: str,
    ) -> Task:
        """Create a new task in the database.

        Args:
            db: Database session.
            task_data: Task data from Sheets.
            row_id: Google Sheets row ID for tracking.

        Returns:
            Created Task instance.
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

        logger.info(
            "Created new task",
            extra={
                "row_id": row_id,
                "level": task.level,
                "type": task.type,
                "status": task.status,
            },
        )

        return task

    def _has_task_changed(self, task: Task, task_data: dict[str, Any]) -> bool:
        """Check if task data has changed compared to database.

        Compares all significant fields to determine if an update is needed.

        Args:
            task: Existing Task instance from database.
            task_data: Task data from Sheets.

        Returns:
            True if any field has changed, False otherwise.
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

    def _update_task(
        self,
        task: Task,
        task_data: dict[str, Any],
        row_id: str,
    ) -> None:
        """Update existing task with data from Sheets.

        Args:
            task: Existing Task instance to update.
            task_data: Task data from Sheets.
            row_id: Google Sheets row ID.
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

        logger.info(
            "Updated task",
            extra={
                "row_id": row_id,
                "level": task.level,
                "type": task.type,
                "status": task.status,
            },
        )
