"""Progress calculation service.

Calculates user learning progress metrics including activity, quality, and level mastery.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.english_tutor.models.progress import Progress
from src.english_tutor.models.question import Question
from src.english_tutor.models.task import Task

# Valid language domains
VALID_DOMAINS = [
    "listening",
    "reading",
    "writing",
    "speaking",
    "grammar",
    "vocabulary",
    "pronunciation",
]

# Valid CEFR levels
VALID_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

# Minimum tasks threshold for level mastery calculation
MIN_TASKS_FOR_MASTERY = 5


class ProgressMetrics:
    """Container for progress metrics."""

    def __init__(self):
        # Activity metrics
        self.completed_tasks_count: int = 0
        self.active_days_this_month: int = 0
        self.current_streak_days: int = 0

        # Quality metrics
        self.overall_accuracy: Optional[float] = None
        self.skill_accuracy: dict[str, Optional[float]] = {domain: None for domain in VALID_DOMAINS}

        # Level mastery
        self.level_mastery: dict[str, Optional[float]] = {level: None for level in VALID_LEVELS}


class ProgressService:
    """Service for calculating user progress metrics."""

    def calculate_progress(self, user_id: str, db: Session) -> ProgressMetrics:
        """Calculate all progress metrics for a user.

        Args:
            user_id: User telegram_user_id
            db: Database session

        Returns:
            ProgressMetrics object with all calculated metrics
        """
        metrics = ProgressMetrics()

        # Get all completed tasks for user
        progress_records = (
            db.query(Progress)
            .filter(Progress.user_id == user_id)
            .order_by(Progress.completed_at.asc())
            .all()
        )

        if not progress_records:
            return metrics

        # Load tasks with their questions for calculations
        task_ids = [p.task_id for p in progress_records]
        tasks = db.query(Task).filter(Task.sheets_row_id.in_(task_ids)).all()
        task_map = {task.sheets_row_id: task for task in tasks}

        # Calculate activity metrics
        self._calculate_activity_metrics(progress_records, metrics)

        # Calculate quality metrics
        self._calculate_quality_metrics(progress_records, task_map, db, metrics)

        # Calculate level mastery
        self._calculate_level_mastery(progress_records, task_map, metrics)

        return metrics

    def _calculate_activity_metrics(
        self, progress_records: list[Progress], metrics: ProgressMetrics
    ) -> None:
        """Calculate activity metrics (completed tasks, active days, streak).

        Args:
            progress_records: List of progress records
            metrics: ProgressMetrics object to update
        """
        metrics.completed_tasks_count = len(progress_records)

        # Calculate active days this month
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        active_days = set()
        all_days = set()

        for progress in progress_records:
            completed_date = progress.completed_at.date()
            all_days.add(completed_date)

            # Check if within current month
            # Ensure both datetimes are timezone-aware for comparison
            completed_at_aware = progress.completed_at
            if completed_at_aware.tzinfo is None:
                completed_at_aware = completed_at_aware.replace(tzinfo=timezone.utc)
            if completed_at_aware >= month_start:
                active_days.add(completed_date)

        metrics.active_days_this_month = len(active_days)

        # Calculate streak (consecutive days with at least one task)
        if not all_days:
            metrics.current_streak_days = 0
            return

        today = date.today()
        streak = 0

        # Start from today and work backwards
        # If today has activity, start counting from today
        # Otherwise, start from yesterday
        current_date = today
        if today not in all_days:
            # If no activity today, check if yesterday had activity
            current_date = today - timedelta(days=1)
            if current_date not in all_days:
                # No activity today or yesterday, streak is 0
                metrics.current_streak_days = 0
                return

        # Count consecutive days backwards
        while current_date in all_days:
            streak += 1
            current_date -= timedelta(days=1)

        metrics.current_streak_days = streak

    def _calculate_quality_metrics(
        self,
        progress_records: list[Progress],
        task_map: dict[str, Task],
        db: Session,
        metrics: ProgressMetrics,
    ) -> None:
        """Calculate quality metrics (overall and skill-specific accuracy).

        Args:
            progress_records: List of progress records
            task_map: Dictionary mapping task_id to Task objects
            db: Database session
            metrics: ProgressMetrics object to update
        """
        total_correct = 0
        total_answers = 0

        # Track answers per skill
        skill_correct: dict[str, int] = defaultdict(int)
        skill_total: dict[str, int] = defaultdict(int)

        for progress in progress_records:
            task = task_map.get(progress.task_id)
            if not task:
                continue

            # Get questions for this task to count total answers
            questions = db.query(Question).filter(Question.task_id == task.sheets_row_id).all()

            if not questions:
                continue

            # Count correct answers for this task
            task_correct = 0
            task_total = 0
            for question in questions:
                question_id_str = question.sheets_row_id
                if question_id_str in progress.answers:
                    user_answer = progress.answers[question_id_str]
                    task_total += 1
                    if user_answer == question.correct_answer:
                        task_correct += 1

            total_correct += task_correct
            total_answers += task_total

            # Track by skill (language_domain)
            if task.language_domain and task.language_domain in VALID_DOMAINS:
                domain = task.language_domain
                skill_total[domain] += task_total
                skill_correct[domain] += task_correct

        # Calculate overall accuracy
        if total_answers > 0:
            metrics.overall_accuracy = (total_correct / total_answers) * 100.0

        # Calculate skill-specific accuracy
        for domain in VALID_DOMAINS:
            if domain in skill_total and skill_total[domain] > 0:
                metrics.skill_accuracy[domain] = (
                    skill_correct[domain] / skill_total[domain]
                ) * 100.0

    def _calculate_level_mastery(
        self,
        progress_records: list[Progress],
        task_map: dict[str, Task],
        metrics: ProgressMetrics,
    ) -> None:
        """Calculate level mastery for each CEFR level.

        Args:
            progress_records: List of progress records
            task_map: Dictionary mapping task_id to Task objects
            metrics: ProgressMetrics object to update
        """
        # Group progress by level
        level_progress: dict[str, list[Progress]] = defaultdict(list)

        for progress in progress_records:
            task = task_map.get(progress.task_id)
            if task and task.level in VALID_LEVELS:
                level_progress[task.level].append(progress)

        # Calculate mastery for each level
        for level in VALID_LEVELS:
            level_records = level_progress.get(level, [])
            if not level_records:
                continue

            # Calculate average accuracy for this level
            total_accuracy = sum(p.percentage_correct for p in level_records)
            avg_accuracy = total_accuracy / len(level_records)

            # Calculate volume factor (based on number of tasks completed)
            task_count = len(level_records)
            volume_factor = min(1.0, task_count / MIN_TASKS_FOR_MASTERY)

            # Mastery = average accuracy * volume factor
            # This ensures users need both high accuracy AND sufficient volume
            metrics.level_mastery[level] = avg_accuracy * volume_factor
