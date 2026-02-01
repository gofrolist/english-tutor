"""Unit tests for task bot handlers.

Tests for Telegram bot handlers in the task delivery flow.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Message, Update
from telegram import User as TelegramUser

from src.english_tutor.api.bot import handle_text_message
from src.english_tutor.api.bot.handlers.tasks import task_command
from src.english_tutor.models.progress import Progress
from src.english_tutor.models.task import Task
from src.english_tutor.models.user import User


class TestTaskCommand:
    """Test suite for task_command handler."""

    @pytest.fixture
    def mock_update(self):
        """Create a mock Update with a Message."""
        update = MagicMock(spec=Update)
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        update.message.reply_text.return_value = MagicMock()
        update.effective_user = MagicMock(spec=TelegramUser)
        update.effective_user.id = 12345
        return update

    @pytest.fixture
    def mock_context(self):
        """Create a mock Context."""
        context = MagicMock()
        context.user_data = {}
        return context

    def _mock_session_local(self, db_session):
        """Helper to create a mock session factory."""
        return lambda: db_session

    @pytest.mark.asyncio
    async def test_task_command_requires_user(self, db_session, mock_update, mock_context):
        """Test that task_command requires user to exist."""
        with patch(
            "src.english_tutor.api.bot.handlers.tasks.get_session_local",
            return_value=self._mock_session_local(db_session),
        ):
            await task_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        assert (
            "Пожалуйста, сначала запустите бота командой /start"
            in (mock_update.message.reply_text.call_args[0][0])
        )

    @pytest.mark.asyncio
    async def test_task_command_requires_level(self, db_session, mock_update, mock_context):
        """Test that task_command requires user to have a level."""
        user = User(telegram_user_id="12345", is_active=True, current_level=None)
        db_session.add(user)
        db_session.commit()

        with patch(
            "src.english_tutor.api.bot.handlers.tasks.get_session_local",
            return_value=self._mock_session_local(db_session),
        ):
            await task_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        assert "/assess" in mock_update.message.reply_text.call_args[0][0]
        assert "оценку" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_task_command_shows_congratulations_when_all_completed_correctly(
        self, db_session, mock_update, mock_context
    ):
        """Test that task_command shows congratulations when all tasks done with 100%."""
        user = User(
            telegram_user_id="12345",
            current_level="B1",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        task = Task(
            sheets_row_id="task_1",
            level="B1",
            type="text",
            title="Task 1",
            content_text="Content 1",
            status="published",
        )
        db_session.add(task)
        db_session.commit()

        progress = Progress(
            user_id=user.telegram_user_id,
            task_id=task.sheets_row_id,
            answers={},
            score=10.0,
            percentage_correct=100.0,
        )
        db_session.add(progress)
        db_session.commit()

        with patch(
            "src.english_tutor.api.bot.handlers.tasks.get_session_local",
            return_value=self._mock_session_local(db_session),
        ):
            await task_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        text = mock_update.message.reply_text.call_args[0][0]
        assert "Поздравляем" in text
        assert "все задания" in text
        assert "/assess" in text
        assert "следующий уровень" in text

    @pytest.mark.asyncio
    async def test_task_command_shows_no_tasks_when_no_tasks_available(
        self, db_session, mock_update, mock_context
    ):
        """Test that task_command shows 'no tasks' message when no tasks exist for level."""
        user = User(
            telegram_user_id="12345",
            current_level="B1",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        # No tasks in DB - select_task_for_user returns None
        # all_tasks_completed_correctly returns False (no tasks = not all completed)
        with patch(
            "src.english_tutor.api.bot.handlers.tasks.get_session_local",
            return_value=self._mock_session_local(db_session),
        ):
            await task_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        text = mock_update.message.reply_text.call_args[0][0]
        assert "Извините" in text or "нет заданий" in text
        assert "Поздравляем" not in text

    @pytest.mark.asyncio
    async def test_handle_text_message_dispatches_to_task_when_in_task_context(
        self, db_session, mock_update, mock_context
    ):
        """Test that handle_text_message routes to handle_task_answer when in task context."""
        mock_update.message.text = "apple"
        mock_context.user_data["current_task_id"] = "task_1"
        mock_context.user_data["current_question_id"] = "q_1"
        mock_context.user_data["current_question_options"] = ["water", "rice", "apple"]

        user = User(
            telegram_user_id="12345",
            current_level="B1",
            is_active=True,
        )
        db_session.add(user)

        task = Task(
            sheets_row_id="task_1",
            level="B1",
            type="text",
            title="Task 1",
            content_text="Content",
            status="published",
        )
        db_session.add(task)

        from src.english_tutor.models.question import Question

        q = Question(
            sheets_row_id="q_1",
            task_id="task_1",
            question_text="Which is countable?",
            answer_options=["water", "rice", "apple"],
            correct_answer=2,
        )
        db_session.add(q)
        db_session.commit()

        with patch(
            "src.english_tutor.api.bot.handlers.tasks.get_session_local",
            return_value=lambda: db_session,
        ):
            await handle_text_message(mock_update, mock_context)

        # handle_task_answer should have run and completed the task (sent feedback)
        assert mock_update.message.reply_text.call_count >= 1
        calls = [c[0][0] for c in mock_update.message.reply_text.call_args_list]
        assert any(
            "✓" in text or "Задание выполнено" in text or "Ответ записан" in text for text in calls
        )
