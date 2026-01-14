"""Unit tests for task delivery service.

Tests for task delivery service level filtering and task selection.
"""

import pytest

from src.english_tutor.models.task import Task
from src.english_tutor.models.user import User
from src.english_tutor.services.task_delivery import TaskDeliveryService
from src.english_tutor.utils.exceptions import TaskDeliveryError


class TestTaskDeliveryService:
    """Test suite for task delivery service."""

    def test_get_tasks_by_level(self, db_session):
        """Test retrieving tasks filtered by user level."""
        # Create tasks at different levels
        task_a2 = Task(
            level="A2",
            type="text",
            title="A2 Task",
            content_text="A2 content",
            status="published",
        )
        task_b1 = Task(
            level="B1",
            type="text",
            title="B1 Task",
            content_text="B1 content",
            status="published",
        )
        task_b2 = Task(
            level="B2",
            type="text",
            title="B2 Task",
            content_text="B2 content",
            status="published",
        )

        db_session.add_all([task_a2, task_b1, task_b2])
        db_session.commit()

        service = TaskDeliveryService()

        # Get tasks for B1 level user
        tasks = service.get_tasks_by_level("B1", db_session)

        # Should return tasks at B1 level or one level above/below
        task_levels = [task.level for task in tasks]
        assert "B1" in task_levels
        assert all(level in ["A2", "B1", "B2"] for level in task_levels)

    def test_get_tasks_by_level_only_published(self, db_session):
        """Test that only published tasks are returned."""
        task_draft = Task(
            level="B1",
            type="text",
            title="Draft Task",
            content_text="Draft content",
            status="draft",
        )
        task_published = Task(
            level="B1",
            type="text",
            title="Published Task",
            content_text="Published content",
            status="published",
        )

        db_session.add_all([task_draft, task_published])
        db_session.commit()

        service = TaskDeliveryService()
        tasks = service.get_tasks_by_level("B1", db_session)

        task_ids = [task.id for task in tasks]
        assert task_published.id in task_ids
        assert task_draft.id not in task_ids

    def test_get_tasks_by_level_and_type(self, db_session):
        """Test filtering tasks by level and type."""
        task_text = Task(
            level="B1",
            type="text",
            title="Text Task",
            content_text="Text content",
            status="published",
        )
        task_audio = Task(
            level="B1",
            type="audio",
            title="Audio Task",
            content_audio_url="https://example.com/audio.mp3",
            status="published",
        )

        db_session.add_all([task_text, task_audio])
        db_session.commit()

        service = TaskDeliveryService()

        text_tasks = service.get_tasks_by_level_and_type("B1", "text", db_session)
        audio_tasks = service.get_tasks_by_level_and_type("B1", "audio", db_session)

        assert len(text_tasks) == 1
        assert text_tasks[0].type == "text"
        assert len(audio_tasks) == 1
        assert audio_tasks[0].type == "audio"

    def test_select_task_for_user(self, db_session):
        """Test selecting a task for a user."""
        user = User(telegram_user_id="11111", current_level="B1", is_active=True)
        db_session.add(user)
        db_session.commit()

        task1 = Task(
            level="B1",
            type="text",
            title="Task 1",
            content_text="Content 1",
            status="published",
        )
        task2 = Task(
            level="B1",
            type="text",
            title="Task 2",
            content_text="Content 2",
            status="published",
        )
        db_session.add_all([task1, task2])
        db_session.commit()

        service = TaskDeliveryService()
        selected_task = service.select_task_for_user(user.id, db_session)

        assert selected_task is not None
        assert selected_task.level in ["A2", "B1", "B2"]
        assert selected_task.status == "published"

    def test_get_tasks_by_level_invalid_level(self, db_session):
        """Test that invalid level raises error."""
        service = TaskDeliveryService()

        with pytest.raises(TaskDeliveryError):
            service.get_tasks_by_level("INVALID", db_session)
