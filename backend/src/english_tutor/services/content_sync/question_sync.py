"""Question synchronization service.

Service for syncing questions from Google Sheets to the database.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.english_tutor.models.question import Question
from src.english_tutor.models.task import Task
from src.english_tutor.services.content_sync.base import SyncStats, log_sync
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)


class QuestionSyncService:
    """Service for syncing questions from Google Sheets to database.

    This service handles the synchronization of question data from Google Sheets,
    matching questions to their parent tasks by task_row_id.

    Example:
        >>> service = QuestionSyncService()
        >>> stats = service.sync_questions(db, questions_data, tasks_by_row_id)
        >>> print(f"Created: {stats['questions_created']}")
    """

    def sync_questions(
        self,
        db: Session,
        questions_data: list[dict[str, Any]],
        tasks_by_row_id: dict[str, dict[str, Any]],
    ) -> SyncStats:
        """Sync questions from Google Sheets to database.

        Processes each question from the sheets data, creating new questions or
        updating existing ones. Questions are matched by their sheets_row_id and
        linked to parent tasks by task_row_id.

        Args:
            db: Database session for persistence operations.
            questions_data: List of question data dictionaries from Sheets.
            tasks_by_row_id: Dictionary mapping task row_id to task data.

        Returns:
            SyncStats with counts of created, updated, skipped, and deleted questions.

        Example:
            >>> service = QuestionSyncService()
            >>> stats = service.sync_questions(db, [{"row_id": "q1", ...}], {"t1": {...}})
            >>> print(f"Created: {stats['questions_created']}")
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

        # Group questions by task_row_id
        questions_by_task = self._group_questions_by_task(questions_data)

        total_tasks = len(questions_by_task)
        log_sync(f"Processing questions for {total_tasks} tasks")

        # Sync questions for each task
        for task_idx, (task_row_id, question_list) in enumerate(questions_by_task.items(), 1):
            try:
                task_stats = self._sync_task_questions(
                    db=db,
                    task_row_id=task_row_id,
                    question_list=question_list,
                    tasks_by_row_id=tasks_by_row_id,
                    task_idx=task_idx,
                    total_tasks=total_tasks,
                )

                # Aggregate stats
                stats["questions_created"] += task_stats.get("questions_created", 0)
                stats["questions_updated"] += task_stats.get("questions_updated", 0)
                stats["questions_skipped"] += task_stats.get("questions_skipped", 0)
                stats["questions_deleted"] += task_stats.get("questions_deleted", 0)

            except Exception as e:
                logger.error(
                    "Error syncing questions for task",
                    extra={"task_row_id": task_row_id, "error": str(e)},
                    exc_info=True,
                )
                log_sync(f"Error questions for task {task_row_id}: {e}", level="error")
                stats["errors"] = stats.get("errors", 0) + 1

        return stats

    def _group_questions_by_task(
        self,
        questions_data: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        """Group questions by their parent task row ID.

        Args:
            questions_data: List of question data from Sheets.

        Returns:
            Dictionary mapping task_row_id to list of questions.
        """
        questions_by_task: dict[str, list[dict[str, Any]]] = {}

        for question_data in questions_data:
            task_row_id = question_data.get("task_row_id")
            if task_row_id:
                if task_row_id not in questions_by_task:
                    questions_by_task[task_row_id] = []
                questions_by_task[task_row_id].append(question_data)

        return questions_by_task

    def _sync_task_questions(
        self,
        db: Session,
        task_row_id: str,
        question_list: list[dict[str, Any]],
        tasks_by_row_id: dict[str, dict[str, Any]],
        task_idx: int,
        total_tasks: int,
    ) -> SyncStats:
        """Sync questions for a single task.

        Args:
            db: Database session.
            task_row_id: Parent task's sheets row ID.
            question_list: List of questions belonging to this task.
            tasks_by_row_id: Dictionary mapping task row_id to task data.
            task_idx: Current task index for progress logging.
            total_tasks: Total number of tasks for progress logging.

        Returns:
            SyncStats for this task's questions.
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

        # Find the parent task in database
        task = self._find_task_by_row_id(db, task_row_id, tasks_by_row_id)

        if not task:
            logger.warning(
                "Task not found in database, skipping questions",
                extra={"task_row_id": task_row_id, "question_count": len(question_list)},
            )
            return stats

        # Get existing questions for this task
        existing_questions = db.query(Question).filter(Question.task_id == task.sheets_row_id).all()
        existing_by_row_id = {q.sheets_row_id: q for q in existing_questions if q.sheets_row_id}

        # Process each question
        for q_idx, question_data in enumerate(question_list, 1):
            row_id = question_data.get("row_id")
            if not row_id:
                continue

            log_sync(f"Processing question [{q_idx}/{len(question_list)}]: {row_id}")

            existing_question = existing_by_row_id.get(row_id)

            if existing_question:
                if self._has_question_changed(existing_question, question_data):
                    self._update_question(existing_question, question_data, row_id)
                    stats["questions_updated"] += 1
                    log_sync(f"Updated question: {row_id}")
                else:
                    stats["questions_skipped"] += 1
                    log_sync(f"Skipped question: {row_id} (no changes)")
            else:
                self._create_question(db, task.sheets_row_id, question_data, row_id)
                stats["questions_created"] += 1
                log_sync(f"Created question: {row_id}")

        return stats

    def _find_task_by_row_id(
        self,
        db: Session,
        row_id: str,
        tasks_by_row_id: dict[str, dict[str, Any]],
    ) -> Optional[Task]:
        """Find task in database by row_id.

        Args:
            db: Database session.
            row_id: Google Sheets row ID.
            tasks_by_row_id: Dictionary mapping task row_id to task data.

        Returns:
            Task instance if found, None otherwise.
        """
        if row_id:
            task = db.query(Task).filter(Task.sheets_row_id == row_id).first()
            if task:
                return task

        return None

    def _create_question(
        self,
        db: Session,
        task_id: str,
        question_data: dict[str, Any],
        row_id: str,
    ) -> Question:
        """Create a new question in the database.

        Args:
            db: Database session.
            task_id: Parent task's sheets_row_id.
            question_data: Question data from Sheets.
            row_id: Google Sheets row ID for tracking.

        Returns:
            Created Question instance.
        """
        question = Question(
            task_id=task_id,
            question_text=question_data["question_text"],
            answer_options=question_data["answer_options"],
            correct_answer=question_data["correct_answer"],
            sheets_row_id=row_id,
        )
        db.add(question)
        db.flush()

        logger.info(
            "Created new question",
            extra={
                "row_id": row_id,
                "task_id": task_id,
            },
        )

        return question

    def _has_question_changed(
        self,
        question: Question,
        question_data: dict[str, Any],
    ) -> bool:
        """Check if question data has changed compared to database.

        Compares all significant fields to determine if an update is needed.

        Args:
            question: Existing Question instance from database.
            question_data: Question data from Sheets.

        Returns:
            True if any field has changed, False otherwise.
        """
        if question.question_text != question_data["question_text"]:
            return True
        if question.answer_options != question_data["answer_options"]:
            return True
        if question.correct_answer != question_data["correct_answer"]:
            return True

        return False

    def _update_question(
        self,
        question: Question,
        question_data: dict[str, Any],
        row_id: str,
    ) -> None:
        """Update existing question with data from Sheets.

        Args:
            question: Existing Question instance to update.
            question_data: Question data from Sheets.
            row_id: Google Sheets row ID.
        """
        question.question_text = question_data["question_text"]
        question.answer_options = question_data["answer_options"]
        question.correct_answer = question_data["correct_answer"]
        question.sheets_row_id = row_id
        question.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        logger.info(
            "Updated question",
            extra={
                "row_id": row_id,
                "task_id": question.task_id,
            },
        )
