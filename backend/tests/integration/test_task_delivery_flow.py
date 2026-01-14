"""Integration tests for task delivery flow.

Tests the complete task delivery flow: request task → receive content → answer questions → get feedback.
"""

from src.english_tutor.models.question import Question
from src.english_tutor.models.task import Task
from src.english_tutor.models.user import User
from src.english_tutor.services.task_completion import TaskCompletionService
from src.english_tutor.services.task_delivery import TaskDeliveryService


class TestTaskDeliveryFlow:
    """Test suite for complete task delivery flow."""

    def test_complete_task_delivery_flow(self, db_session):
        """Test complete task delivery flow from request to feedback."""
        # Step 1: User with determined level
        user = User(telegram_user_id="12345", current_level="B1", is_active=True)
        db_session.add(user)
        db_session.commit()

        # Step 2: Create a task with questions
        task = Task(
            level="B1",
            type="text",
            title="Grammar: Past Simple",
            content_text="The past simple tense is used to describe completed actions.",
            explanation="Use past simple for actions that happened in the past.",
            status="published",
        )
        db_session.add(task)
        db_session.commit()

        question1 = Question(
            task_id=task.id,
            question_text="What is the past tense of 'go'?",
            answer_options=["goed", "went", "gone", "going"],
            correct_answer=1,
            order=1,
        )
        question2 = Question(
            task_id=task.id,
            question_text="What is the past tense of 'eat'?",
            answer_options=["eated", "ate", "eaten", "eating"],
            correct_answer=1,
            order=2,
        )
        db_session.add_all([question1, question2])
        db_session.commit()

        # Step 3: Request task
        delivery_service = TaskDeliveryService()
        selected_task = delivery_service.select_task_for_user(user.id, db_session)

        assert selected_task.id == task.id
        assert selected_task.type == "text"
        assert selected_task.content_text is not None

        # Step 4: User answers questions
        answers = {
            str(question1.id): 1,  # correct
            str(question2.id): 0,  # incorrect
        }

        # Step 5: Complete task and get feedback
        completion_service = TaskCompletionService()
        progress = completion_service.complete_task(
            user.id,
            task.id,
            answers,
            db_session,
        )

        assert progress.user_id == user.id
        assert progress.task_id == task.id
        assert progress.answers == answers
        assert progress.score >= 0
        assert 0 <= progress.percentage_correct <= 100
        assert progress.completed_at is not None

    def test_task_delivery_audio_task(self, db_session):
        """Test delivering an audio task."""
        user = User(telegram_user_id="67890", current_level="A2", is_active=True)
        db_session.add(user)
        db_session.commit()

        task = Task(
            level="A2",
            type="audio",
            title="Listening: Daily Routine",
            content_audio_url="https://example.com/audio.mp3",
            status="published",
        )
        db_session.add(task)
        db_session.commit()

        delivery_service = TaskDeliveryService()
        selected_task = delivery_service.select_task_for_user(user.id, db_session)

        assert selected_task.type == "audio"
        assert selected_task.content_audio_url is not None

    def test_task_delivery_video_task(self, db_session):
        """Test delivering a video task."""
        user = User(telegram_user_id="99999", current_level="C1", is_active=True)
        db_session.add(user)
        db_session.commit()

        task = Task(
            level="C1",
            type="video",
            title="Video: Academic Presentation",
            content_video_url="https://example.com/video.mp4",
            status="published",
        )
        db_session.add(task)
        db_session.commit()

        delivery_service = TaskDeliveryService()
        selected_task = delivery_service.select_task_for_user(user.id, db_session)

        assert selected_task.type == "video"
        assert selected_task.content_video_url is not None
