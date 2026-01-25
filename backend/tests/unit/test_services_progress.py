"""Unit tests for progress calculation service.

Tests for progress metrics calculation including activity, quality, and level mastery.
"""

from datetime import date, datetime, timedelta, timezone

from src.english_tutor.models.progress import Progress
from src.english_tutor.models.question import Question
from src.english_tutor.models.task import Task, TaskStatus, TaskType
from src.english_tutor.models.user import User
from src.english_tutor.services.progress import ProgressService


class TestProgressService:
    """Test suite for progress calculation service."""

    def test_calculate_progress_no_data(self, db_session):
        """Test progress calculation with no completed tasks."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        service = ProgressService()
        metrics = service.calculate_progress(user.telegram_user_id, db_session)

        assert metrics.completed_tasks_count == 0
        assert metrics.active_days_this_month == 0
        assert metrics.current_streak_days == 0
        assert metrics.overall_accuracy is None
        assert all(acc is None for acc in metrics.skill_accuracy.values())
        assert all(mastery is None for mastery in metrics.level_mastery.values())

    def test_calculate_completed_tasks_count(self, db_session):
        """Test counting completed tasks."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)

        # Create tasks
        task1 = Task(
            sheets_row_id="task-001",
            level="A1",
            type=TaskType.TEXT.value,
            title="Task 1",
            content_text="Content 1",
            status=TaskStatus.PUBLISHED.value,
        )
        task2 = Task(
            sheets_row_id="task-002",
            level="A2",
            type=TaskType.AUDIO.value,
            content_url="http://example.com/audio.mp3",
            title="Task 2",
            status=TaskStatus.PUBLISHED.value,
        )
        db_session.add_all([task1, task2])
        db_session.commit()

        # Create progress records
        progress1 = Progress(
            user_id=user.telegram_user_id,
            task_id=task1.sheets_row_id,
            answers={},
            score=10.0,
            percentage_correct=100.0,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        progress2 = Progress(
            user_id=user.telegram_user_id,
            task_id=task2.sheets_row_id,
            answers={},
            score=8.0,
            percentage_correct=80.0,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db_session.add_all([progress1, progress2])
        db_session.commit()

        service = ProgressService()
        metrics = service.calculate_progress(user.telegram_user_id, db_session)

        assert metrics.completed_tasks_count == 2

    def test_calculate_active_days_this_month(self, db_session):
        """Test calculating active days in current month."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)

        # Create multiple tasks to avoid unique constraint
        task1 = Task(
            sheets_row_id="task-001",
            level="A1",
            type=TaskType.TEXT.value,
            title="Task 1",
            content_text="Content 1",
            status=TaskStatus.PUBLISHED.value,
        )
        task2 = Task(
            sheets_row_id="task-002",
            level="A1",
            type=TaskType.TEXT.value,
            title="Task 2",
            content_text="Content 2",
            status=TaskStatus.PUBLISHED.value,
        )
        task3 = Task(
            sheets_row_id="task-003",
            level="A1",
            type=TaskType.TEXT.value,
            title="Task 3",
            content_text="Content 3",
            status=TaskStatus.PUBLISHED.value,
        )
        db_session.add_all([task1, task2, task3])
        db_session.commit()

        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Create progress on different days this month (using different tasks)
        progress1 = Progress(
            user_id=user.telegram_user_id,
            task_id=task1.sheets_row_id,
            answers={},
            score=10.0,
            percentage_correct=100.0,
            completed_at=(month_start + timedelta(days=1)).replace(tzinfo=None),
        )
        progress2 = Progress(
            user_id=user.telegram_user_id,
            task_id=task2.sheets_row_id,
            answers={},
            score=10.0,
            percentage_correct=100.0,
            completed_at=(month_start + timedelta(days=1)).replace(tzinfo=None),  # Same day
        )
        progress3 = Progress(
            user_id=user.telegram_user_id,
            task_id=task3.sheets_row_id,
            answers={},
            score=10.0,
            percentage_correct=100.0,
            completed_at=(month_start + timedelta(days=5)).replace(tzinfo=None),  # Different day
        )
        db_session.add_all([progress1, progress2, progress3])
        db_session.commit()

        service = ProgressService()
        metrics = service.calculate_progress(user.telegram_user_id, db_session)

        # Should count 2 unique days (day 1 and day 5)
        assert metrics.active_days_this_month == 2

    def test_calculate_streak_consecutive_days(self, db_session):
        """Test calculating consecutive day streak."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)

        # Create multiple tasks to avoid unique constraint
        tasks = []
        for i in range(5):
            task = Task(
                sheets_row_id=f"task-{i:03d}",
                level="A1",
                type=TaskType.TEXT.value,
                title=f"Task {i}",
                content_text=f"Content {i}",
                status=TaskStatus.PUBLISHED.value,
            )
            tasks.append(task)
        db_session.add_all(tasks)
        db_session.commit()

        today = date.today()

        # Create progress for consecutive days ending today (using different tasks)
        for i in range(5):
            progress = Progress(
                user_id=user.telegram_user_id,
                task_id=tasks[i].sheets_row_id,
                answers={},
                score=10.0,
                percentage_correct=100.0,
                completed_at=datetime.combine(
                    today - timedelta(days=i), datetime.min.time()
                ).replace(tzinfo=None),
            )
            db_session.add(progress)

        db_session.commit()

        service = ProgressService()
        metrics = service.calculate_progress(user.telegram_user_id, db_session)

        assert metrics.current_streak_days == 5

    def test_calculate_streak_broken(self, db_session):
        """Test that streak resets when a day is skipped."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)

        task1 = Task(
            sheets_row_id="task-001",
            level="A1",
            type=TaskType.TEXT.value,
            title="Task 1",
            content_text="Content 1",
            status=TaskStatus.PUBLISHED.value,
        )
        task2 = Task(
            sheets_row_id="task-002",
            level="A1",
            type=TaskType.TEXT.value,
            title="Task 2",
            content_text="Content 2",
            status=TaskStatus.PUBLISHED.value,
        )
        db_session.add_all([task1, task2])
        db_session.commit()

        today = date.today()

        # Create progress with a gap (missing yesterday)
        progress_today = Progress(
            user_id=user.telegram_user_id,
            task_id=task1.sheets_row_id,
            answers={},
            score=10.0,
            percentage_correct=100.0,
            completed_at=datetime.combine(today, datetime.min.time()).replace(tzinfo=None),
        )
        progress_3_days_ago = Progress(
            user_id=user.telegram_user_id,
            task_id=task2.sheets_row_id,
            answers={},
            score=10.0,
            percentage_correct=100.0,
            completed_at=datetime.combine(today - timedelta(days=3), datetime.min.time()).replace(
                tzinfo=None
            ),
        )
        db_session.add_all([progress_today, progress_3_days_ago])
        db_session.commit()

        service = ProgressService()
        metrics = service.calculate_progress(user.telegram_user_id, db_session)

        # Streak should only be 1 (just today)
        assert metrics.current_streak_days == 1

    def test_calculate_overall_accuracy(self, db_session):
        """Test calculating overall accuracy across all tasks."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)

        task = Task(
            sheets_row_id="task-001",
            level="A1",
            type=TaskType.TEXT.value,
            title="Task 1",
            content_text="Content 1",
            status=TaskStatus.PUBLISHED.value,
        )
        db_session.add(task)

        # Create questions
        q1 = Question(
            sheets_row_id="q1",
            task_id=task.sheets_row_id,
            question_text="Q1?",
            answer_options=["A", "B"],
            correct_answer=0,
            weight=1.0,
        )
        q2 = Question(
            sheets_row_id="q2",
            task_id=task.sheets_row_id,
            question_text="Q2?",
            answer_options=["A", "B"],
            correct_answer=1,
            weight=1.0,
        )
        db_session.add_all([q1, q2])
        db_session.commit()

        # Create progress with 1 correct, 1 incorrect
        progress = Progress(
            user_id=user.telegram_user_id,
            task_id=task.sheets_row_id,
            answers={"q1": 0, "q2": 0},  # q1 correct, q2 incorrect
            score=1.0,
            percentage_correct=50.0,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db_session.add(progress)
        db_session.commit()

        service = ProgressService()
        metrics = service.calculate_progress(user.telegram_user_id, db_session)

        assert metrics.overall_accuracy == 50.0

    def test_calculate_skill_specific_accuracy(self, db_session):
        """Test calculating accuracy per language skill."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)

        # Create tasks with different language domains
        grammar_task = Task(
            sheets_row_id="task-grammar",
            level="A1",
            type=TaskType.TEXT.value,
            title="Grammar Task",
            content_text="Content",
            language_domain="grammar",
            status=TaskStatus.PUBLISHED.value,
        )
        vocab_task = Task(
            sheets_row_id="task-vocab",
            level="A1",
            type=TaskType.TEXT.value,
            title="Vocab Task",
            content_text="Content",
            language_domain="vocabulary",
            status=TaskStatus.PUBLISHED.value,
        )
        db_session.add_all([grammar_task, vocab_task])

        # Create questions
        gq = Question(
            sheets_row_id="gq1",
            task_id=grammar_task.sheets_row_id,
            question_text="Grammar Q?",
            answer_options=["A", "B"],
            correct_answer=0,
            weight=1.0,
        )
        vq = Question(
            sheets_row_id="vq1",
            task_id=vocab_task.sheets_row_id,
            question_text="Vocab Q?",
            answer_options=["A", "B"],
            correct_answer=0,
            weight=1.0,
        )
        db_session.add_all([gq, vq])
        db_session.commit()

        # Grammar: 100% correct
        grammar_progress = Progress(
            user_id=user.telegram_user_id,
            task_id=grammar_task.sheets_row_id,
            answers={"gq1": 0},  # correct
            score=1.0,
            percentage_correct=100.0,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        # Vocabulary: 0% correct
        vocab_progress = Progress(
            user_id=user.telegram_user_id,
            task_id=vocab_task.sheets_row_id,
            answers={"vq1": 1},  # incorrect
            score=0.0,
            percentage_correct=0.0,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db_session.add_all([grammar_progress, vocab_progress])
        db_session.commit()

        service = ProgressService()
        metrics = service.calculate_progress(user.telegram_user_id, db_session)

        assert metrics.skill_accuracy["grammar"] == 100.0
        assert metrics.skill_accuracy["vocabulary"] == 0.0
        assert metrics.skill_accuracy["listening"] is None  # No tasks for this skill

    def test_calculate_level_mastery(self, db_session):
        """Test calculating level mastery with accuracy and volume."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)

        # Create 5 different tasks to avoid unique constraint
        tasks = []
        for i in range(5):
            task = Task(
                sheets_row_id=f"task-{i:03d}",
                level="A1",
                type=TaskType.TEXT.value,
                title=f"Task {i}",
                content_text=f"Content {i}",
                status=TaskStatus.PUBLISHED.value,
            )
            tasks.append(task)
        db_session.add_all(tasks)
        db_session.commit()

        # Create 5 progress records with 80% accuracy each (using different tasks)
        for i in range(5):
            progress = Progress(
                user_id=user.telegram_user_id,
                task_id=tasks[i].sheets_row_id,
                answers={},
                score=8.0,
                percentage_correct=80.0,
                completed_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=i),
            )
            db_session.add(progress)

        db_session.commit()

        service = ProgressService()
        metrics = service.calculate_progress(user.telegram_user_id, db_session)

        # With 5 tasks at 80% accuracy, volume factor = 1.0 (5/5)
        # Mastery = 80.0 * 1.0 = 80.0
        assert metrics.level_mastery["A1"] == 80.0

    def test_calculate_level_mastery_with_volume_factor(self, db_session):
        """Test that level mastery is reduced when task count is below threshold."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)

        # Create 2 different tasks to avoid unique constraint
        task1 = Task(
            sheets_row_id="task-001",
            level="A1",
            type=TaskType.TEXT.value,
            title="Task 1",
            content_text="Content 1",
            status=TaskStatus.PUBLISHED.value,
        )
        task2 = Task(
            sheets_row_id="task-002",
            level="A1",
            type=TaskType.TEXT.value,
            title="Task 2",
            content_text="Content 2",
            status=TaskStatus.PUBLISHED.value,
        )
        db_session.add_all([task1, task2])
        db_session.commit()

        # Create only 2 progress records (below threshold of 5)
        progress1 = Progress(
            user_id=user.telegram_user_id,
            task_id=task1.sheets_row_id,
            answers={},
            score=10.0,
            percentage_correct=100.0,  # Perfect accuracy
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        progress2 = Progress(
            user_id=user.telegram_user_id,
            task_id=task2.sheets_row_id,
            answers={},
            score=10.0,
            percentage_correct=100.0,  # Perfect accuracy
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1),
        )
        db_session.add_all([progress1, progress2])
        db_session.commit()

        service = ProgressService()
        metrics = service.calculate_progress(user.telegram_user_id, db_session)

        # With 2 tasks at 100% accuracy, volume factor = 0.4 (2/5)
        # Mastery = 100.0 * 0.4 = 40.0
        assert metrics.level_mastery["A1"] == 40.0

    def test_calculate_progress_multiple_levels(self, db_session):
        """Test progress calculation across multiple CEFR levels."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)

        a1_task = Task(
            sheets_row_id="task-a1",
            level="A1",
            type=TaskType.TEXT.value,
            title="A1 Task",
            content_text="Content",
            status=TaskStatus.PUBLISHED.value,
        )
        b1_task = Task(
            sheets_row_id="task-b1",
            level="B1",
            type=TaskType.TEXT.value,
            title="B1 Task",
            content_text="Content",
            status=TaskStatus.PUBLISHED.value,
        )
        db_session.add_all([a1_task, b1_task])
        db_session.commit()

        a1_progress = Progress(
            user_id=user.telegram_user_id,
            task_id=a1_task.sheets_row_id,
            answers={},
            score=10.0,
            percentage_correct=100.0,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        b1_progress = Progress(
            user_id=user.telegram_user_id,
            task_id=b1_task.sheets_row_id,
            answers={},
            score=8.0,
            percentage_correct=80.0,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db_session.add_all([a1_progress, b1_progress])
        db_session.commit()

        service = ProgressService()
        metrics = service.calculate_progress(user.telegram_user_id, db_session)

        # A1: 1 task at 100%, volume factor = 0.2, mastery = 20.0
        assert metrics.level_mastery["A1"] == 20.0
        # B1: 1 task at 80%, volume factor = 0.2, mastery = 16.0
        assert metrics.level_mastery["B1"] == 16.0
        # Other levels should be None
        assert metrics.level_mastery["A2"] is None
        assert metrics.level_mastery["B2"] is None

    def test_calculate_progress_ignores_tasks_without_domain(self, db_session):
        """Test that tasks without language_domain don't affect skill accuracy."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)

        task_no_domain = Task(
            sheets_row_id="task-no-domain",
            level="A1",
            type=TaskType.TEXT.value,
            title="Task",
            content_text="Content",
            language_domain=None,
            status=TaskStatus.PUBLISHED.value,
        )
        db_session.add(task_no_domain)

        q = Question(
            sheets_row_id="q1",
            task_id=task_no_domain.sheets_row_id,
            question_text="Q?",
            answer_options=["A", "B"],
            correct_answer=0,
            weight=1.0,
        )
        db_session.add(q)
        db_session.commit()

        progress = Progress(
            user_id=user.telegram_user_id,
            task_id=task_no_domain.sheets_row_id,
            answers={"q1": 0},
            score=1.0,
            percentage_correct=100.0,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db_session.add(progress)
        db_session.commit()

        service = ProgressService()
        metrics = service.calculate_progress(user.telegram_user_id, db_session)

        # Should still calculate overall accuracy
        assert metrics.overall_accuracy == 100.0
        # But skill accuracies should all be None
        assert all(acc is None for acc in metrics.skill_accuracy.values())
