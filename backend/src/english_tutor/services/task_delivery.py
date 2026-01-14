"""Task delivery service.

Service for delivering learning tasks to users based on their proficiency level.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.english_tutor.models.task import Task, TaskStatus, TaskType
from src.english_tutor.models.user import User
from src.english_tutor.utils.exceptions import TaskDeliveryError
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)

# Level ordering for filtering (adjacent levels)
LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


class TaskDeliveryService:
    """Service for task delivery operations."""

    def get_tasks_by_level(self, level: str, db: Session) -> list[Task]:
        """Get tasks filtered by user level.

        Returns tasks at the user's level and one level above/below.

        Args:
            level: User's English proficiency level (A1-C2)
            db: Database session

        Returns:
            List of Task objects matching the level criteria

        Raises:
            TaskDeliveryError: If level is invalid
        """
        if level not in LEVEL_ORDER:
            logger.error("Invalid level requested", extra={"level": level})
            raise TaskDeliveryError(f"Invalid level: {level}")

        level_idx = LEVEL_ORDER.index(level)
        # Get current level and adjacent levels (within bounds)
        valid_levels = [LEVEL_ORDER[level_idx]]
        if level_idx > 0:
            valid_levels.append(LEVEL_ORDER[level_idx - 1])
        if level_idx < len(LEVEL_ORDER) - 1:
            valid_levels.append(LEVEL_ORDER[level_idx + 1])

        tasks = (
            db.query(Task)
            .filter(
                and_(
                    Task.level.in_(valid_levels),
                    Task.status == TaskStatus.PUBLISHED.value,
                )
            )
            .all()
        )

        logger.info(
            "Tasks retrieved by level",
            extra={"level": level, "valid_levels": valid_levels, "count": len(tasks)},
        )

        return tasks

    def get_tasks_by_level_and_type(self, level: str, task_type: str, db: Session) -> list[Task]:
        """Get tasks filtered by level and type.

        Args:
            level: User's English proficiency level (A1-C2)
            task_type: Task type (text, audio, video)
            db: Database session

        Returns:
            List of Task objects matching the level and type criteria

        Raises:
            TaskDeliveryError: If level or type is invalid
        """
        if level not in LEVEL_ORDER:
            raise TaskDeliveryError(f"Invalid level: {level}")

        if task_type not in [TaskType.TEXT.value, TaskType.AUDIO.value, TaskType.VIDEO.value]:
            raise TaskDeliveryError(f"Invalid task type: {task_type}")

        level_idx = LEVEL_ORDER.index(level)
        valid_levels = [LEVEL_ORDER[level_idx]]
        if level_idx > 0:
            valid_levels.append(LEVEL_ORDER[level_idx - 1])
        if level_idx < len(LEVEL_ORDER) - 1:
            valid_levels.append(LEVEL_ORDER[level_idx + 1])

        tasks = (
            db.query(Task)
            .filter(
                and_(
                    Task.level.in_(valid_levels),
                    Task.type == task_type,
                    Task.status == TaskStatus.PUBLISHED.value,
                )
            )
            .all()
        )

        logger.info(
            "Tasks retrieved by level and type",
            extra={"level": level, "type": task_type, "count": len(tasks)},
        )

        return tasks

    def select_task_for_user(self, user_id: UUID, db: Session) -> Optional[Task]:
        """Select a task for a user based on their level.

        Selects a random published task appropriate for the user's level.

        Args:
            user_id: User ID
            db: Database session

        Returns:
            Task object or None if no tasks available

        Raises:
            TaskDeliveryError: If user not found or has no level
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error("User not found", extra={"user_id": str(user_id)})
            raise TaskDeliveryError(f"User not found: {user_id}")

        if not user.current_level:
            logger.error("User has no level assigned", extra={"user_id": str(user_id)})
            raise TaskDeliveryError(f"User has no level assigned: {user_id}")

        tasks = self.get_tasks_by_level(user.current_level, db)

        if not tasks:
            logger.warning("No tasks available for user level", extra={"level": user.current_level})
            return None

        # For now, select the first task (can be enhanced with randomization)
        selected_task = tasks[0]

        logger.info(
            "Task selected for user",
            extra={
                "user_id": str(user_id),
                "task_id": str(selected_task.id),
                "level": user.current_level,
            },
        )

        return selected_task
