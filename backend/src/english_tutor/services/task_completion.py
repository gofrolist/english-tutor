"""Task completion service.

Service for processing task completion and calculating scores.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.english_tutor.models.progress import Progress
from src.english_tutor.models.question import Question
from src.english_tutor.models.task import Task
from src.english_tutor.models.user import User
from src.english_tutor.utils.exceptions import TaskDeliveryError
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)


class TaskCompletionService:
    """Service for task completion operations."""

    def complete_task(
        self,
        user_id: str,
        task_id: str,
        answers: dict[str, int],
        db: Session,
    ) -> Progress:
        """Complete a task and calculate score.

        Args:
            user_id: User telegram_user_id
            task_id: Task sheets_row_id
            answers: Dictionary mapping question sheets_row_ids (as strings) to answer indices
            db: Database session

        Returns:
            Progress object with calculated score

        Raises:
            TaskDeliveryError: If user, task, or questions not found
        """
        user = db.query(User).filter(User.telegram_user_id == user_id).first()
        if not user:
            logger.error("User not found for task completion", extra={"user_id": user_id})
            raise TaskDeliveryError(f"User not found: {user_id}")

        task = db.query(Task).filter(Task.sheets_row_id == task_id).first()
        if not task:
            logger.error("Task not found", extra={"task_id": task_id})
            raise TaskDeliveryError(f"Task not found: {task_id}")

        questions = (
            db.query(Question)
            .filter(Question.task_id == task_id)
            .order_by(Question.sheets_row_id)
            .all()
        )
        if not questions:
            logger.error("No questions found for task", extra={"task_id": task_id})
            raise TaskDeliveryError(f"No questions found for task: {task_id}")

        # Calculate score (count of correct answers; percentage of answered questions)
        total_answered = 0
        correct_count = 0

        for question in questions:
            question_id_str = question.sheets_row_id
            if question_id_str in answers:
                total_answered += 1
                if answers[question_id_str] == question.correct_answer:
                    correct_count += 1

        score = float(correct_count)
        percentage_correct = (correct_count / total_answered * 100.0) if total_answered > 0 else 0.0

        # Check for existing progress
        existing_progress = (
            db.query(Progress)
            .filter(
                Progress.user_id == user_id,
                Progress.task_id == task_id,
            )
            .first()
        )

        if existing_progress:
            # Update existing progress
            existing_progress.answers = answers
            existing_progress.score = score
            existing_progress.percentage_correct = percentage_correct
            existing_progress.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            progress = existing_progress
        else:
            # Create new progress
            progress = Progress(
                user_id=user_id,
                task_id=task_id,
                answers=answers,
                score=score,
                percentage_correct=percentage_correct,
                completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            db.add(progress)

        db.commit()
        db.refresh(progress)

        logger.info(
            "Task completed",
            extra={
                "user_id": user_id,
                "task_id": task_id,
                "score": score,
                "percentage_correct": percentage_correct,
            },
        )

        return progress
