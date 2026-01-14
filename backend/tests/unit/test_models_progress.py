"""Unit tests for Progress model.

Tests for Progress model creation and validation.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from src.english_tutor.models.progress import Progress
from src.english_tutor.models.task import Task
from src.english_tutor.models.user import User


class TestProgressModel:
    """Test suite for Progress model."""

    def test_progress_creation_with_required_fields(self, db_session):
        """Test creating a progress record with required fields."""
        user = User(telegram_user_id="11111", is_active=True)
        db_session.add(user)
        db_session.commit()

        task = Task(
            level="B1",
            type="text",
            title="Test Task",
            content_text="Test content",
            status="published",
        )
        db_session.add(task)
        db_session.commit()

        progress = Progress(
            user_id=user.id,
            task_id=task.id,
            answers={"q1": 0, "q2": 1},
            score=75.5,
            percentage_correct=75.0,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db_session.add(progress)
        db_session.commit()

        assert progress.id is not None
        assert progress.user_id == user.id
        assert progress.task_id == task.id
        assert progress.answers == {"q1": 0, "q2": 1}
        assert progress.score == 75.5
        assert progress.percentage_correct == 75.0
        assert progress.completed_at is not None

    def test_progress_score_non_negative(self, db_session):
        """Test that progress score must be non-negative."""
        user = User(telegram_user_id="22222", is_active=True)
        db_session.add(user)
        db_session.commit()

        task = Task(
            level="B1",
            type="text",
            title="Test Task",
            content_text="Test content",
            status="published",
        )
        db_session.add(task)
        db_session.commit()

        progress = Progress(
            user_id=user.id,
            task_id=task.id,
            answers={},
            score=-10.0,
            percentage_correct=0.0,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db_session.add(progress)

        # This should raise a validation error or database constraint
        with pytest.raises((ValueError, IntegrityError)):
            db_session.commit()

    def test_progress_percentage_correct_range(self, db_session):
        """Test that percentage_correct must be between 0 and 100."""
        user = User(telegram_user_id="33333", is_active=True)
        db_session.add(user)
        db_session.commit()

        task = Task(
            level="B1",
            type="text",
            title="Test Task",
            content_text="Test content",
            status="published",
        )
        db_session.add(task)
        db_session.commit()

        # Valid percentages
        for percentage in [0.0, 50.0, 100.0]:
            progress = Progress(
                user_id=user.id,
                task_id=task.id,
                answers={},
                score=percentage,
                percentage_correct=percentage,
                completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            db_session.add(progress)
            db_session.commit()
            assert progress.percentage_correct == percentage
            db_session.delete(progress)
            db_session.commit()

    def test_progress_relationship_to_user(self, db_session):
        """Test that progress belongs to a user."""
        user = User(telegram_user_id="44444", is_active=True)
        db_session.add(user)
        db_session.commit()

        task = Task(
            level="B1",
            type="text",
            title="Test Task",
            content_text="Test content",
            status="published",
        )
        db_session.add(task)
        db_session.commit()

        progress = Progress(
            user_id=user.id,
            task_id=task.id,
            answers={},
            score=80.0,
            percentage_correct=80.0,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db_session.add(progress)
        db_session.commit()

        assert progress.user_id == user.id
        assert progress in user.progress_records

    def test_progress_relationship_to_task(self, db_session):
        """Test that progress belongs to a task."""
        user = User(telegram_user_id="55555", is_active=True)
        db_session.add(user)
        db_session.commit()

        task = Task(
            level="B1",
            type="text",
            title="Test Task",
            content_text="Test content",
            status="published",
        )
        db_session.add(task)
        db_session.commit()

        progress = Progress(
            user_id=user.id,
            task_id=task.id,
            answers={},
            score=90.0,
            percentage_correct=90.0,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db_session.add(progress)
        db_session.commit()

        assert progress.task_id == task.id
