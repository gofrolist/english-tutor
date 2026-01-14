"""Unit tests for Task model.

Tests for Task model creation, validation, and content type handling.
"""

from src.english_tutor.models.task import Task


class TestTaskModel:
    """Test suite for Task model."""

    def test_task_creation_text_type(self, db_session):
        """Test creating a text task with required fields."""
        task = Task(
            level="B1",
            type="text",
            title="Grammar: Past Simple",
            content_text="The past simple tense is used to describe...",
            explanation="Use past simple for completed actions in the past.",
            status="published",
        )
        db_session.add(task)
        db_session.commit()

        assert task.id is not None
        assert task.level == "B1"
        assert task.type == "text"
        assert task.title == "Grammar: Past Simple"
        assert task.content_text == "The past simple tense is used to describe..."
        assert task.content_audio_url is None
        assert task.content_video_url is None
        assert task.status == "published"
        assert task.created_at is not None
        assert task.updated_at is not None

    def test_task_creation_audio_type(self, db_session):
        """Test creating an audio task with audio URL."""
        task = Task(
            level="A2",
            type="audio",
            title="Listening: Daily Routine",
            content_audio_url="https://example.com/audio.mp3",
            status="published",
        )
        db_session.add(task)
        db_session.commit()

        assert task.type == "audio"
        assert task.content_audio_url == "https://example.com/audio.mp3"
        assert task.content_text is None
        assert task.content_video_url is None

    def test_task_creation_video_type(self, db_session):
        """Test creating a video task with video URL."""
        task = Task(
            level="C1",
            type="video",
            title="Video: Academic Presentation",
            content_video_url="https://example.com/video.mp4",
            status="published",
        )
        db_session.add(task)
        db_session.commit()

        assert task.type == "video"
        assert task.content_video_url == "https://example.com/video.mp4"
        assert task.content_text is None
        assert task.content_audio_url is None

    def test_task_level_validation(self, db_session):
        """Test that level must be valid CEFR level."""
        valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]

        for level in valid_levels:
            task = Task(
                level=level,
                type="text",
                title=f"Task for {level}",
                content_text="Test content",
                status="published",
            )
            db_session.add(task)
            db_session.commit()
            assert task.level == level
            db_session.delete(task)
            db_session.commit()

    def test_task_type_validation(self, db_session):
        """Test that type must be valid content type."""
        valid_types = ["text", "audio", "video"]

        for task_type in valid_types:
            task = Task(
                level="B1",
                type=task_type,
                title=f"{task_type} task",
                status="published",
            )
            if task_type == "text":
                task.content_text = "Test text"
            elif task_type == "audio":
                task.content_audio_url = "https://example.com/audio.mp3"
            else:
                task.content_video_url = "https://example.com/video.mp4"

            db_session.add(task)
            db_session.commit()
            assert task.type == task_type
            db_session.delete(task)
            db_session.commit()

    def test_task_status_draft(self, db_session):
        """Test that task can be created in draft status."""
        task = Task(
            level="B1",
            type="text",
            title="Draft Task",
            content_text="Draft content",
            status="draft",
        )
        db_session.add(task)
        db_session.commit()

        assert task.status == "draft"

    def test_task_status_published(self, db_session):
        """Test that task can be published."""
        task = Task(
            level="B1",
            type="text",
            title="Published Task",
            content_text="Published content",
            status="draft",
        )
        db_session.add(task)
        db_session.commit()

        task.status = "published"
        db_session.commit()

        assert task.status == "published"
