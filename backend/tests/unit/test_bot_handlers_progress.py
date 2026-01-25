"""Unit tests for progress bot handler.

Tests for /progress command handler and progress display.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Message, Update
from telegram import User as TelegramUser

from src.english_tutor.api.bot.handlers.progress import progress_command
from src.english_tutor.models.progress import Progress
from src.english_tutor.models.question import Question
from src.english_tutor.models.task import Task, TaskStatus, TaskType
from src.english_tutor.models.user import User


class TestProgressHandler:
    """Test suite for progress bot handler."""

    @pytest.fixture
    def mock_update(self):
        """Create a mock Update with a Message."""
        update = MagicMock(spec=Update)
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        update.message.reply_text.return_value = MagicMock()
        update.effective_message = update.message
        update.effective_user = MagicMock(spec=TelegramUser)
        update.effective_user.id = 12345
        return update

    @pytest.fixture
    def mock_context(self):
        """Create a mock Context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_progress_command_user_not_found(self, db_session, mock_update, mock_context):
        """Test progress command when user doesn't exist."""
        with patch("src.english_tutor.api.bot.handlers.progress.get_session_local") as mock_session:
            mock_session.return_value = lambda: db_session

            await progress_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "не зарегистрированы" in call_args or "not registered" in call_args.lower()

    @pytest.mark.asyncio
    async def test_progress_command_displays_activity_metrics(
        self, db_session, mock_update, mock_context
    ):
        """Test that progress command displays activity metrics."""
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

        with patch("src.english_tutor.api.bot.handlers.progress.get_session_local") as mock_session:
            mock_session.return_value = lambda: db_session

            await progress_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Выполнено заданий" in call_args or "Tasks completed" in call_args
            assert "Активных дней" in call_args or "Active days" in call_args
            assert "серия" in call_args or "streak" in call_args.lower()

    @pytest.mark.asyncio
    async def test_progress_command_displays_quality_metrics(
        self, db_session, mock_update, mock_context
    ):
        """Test that progress command displays quality metrics."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)

        task = Task(
            sheets_row_id="task-001",
            level="A1",
            type=TaskType.TEXT.value,
            title="Task 1",
            content_text="Content 1",
            language_domain="grammar",
            status=TaskStatus.PUBLISHED.value,
        )
        db_session.add(task)

        q = Question(
            sheets_row_id="q1",
            task_id=task.sheets_row_id,
            question_text="Q?",
            answer_options=["A", "B"],
            correct_answer=0,
            weight=1.0,
        )
        db_session.add(q)
        db_session.commit()

        progress = Progress(
            user_id=user.telegram_user_id,
            task_id=task.sheets_row_id,
            answers={"q1": 0},
            score=1.0,
            percentage_correct=100.0,
        )
        db_session.add(progress)
        db_session.commit()

        with patch("src.english_tutor.api.bot.handlers.progress.get_session_local") as mock_session:
            mock_session.return_value = lambda: db_session

            await progress_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "точность" in call_args.lower() or "accuracy" in call_args.lower()
            assert "Грамматика" in call_args or "Grammar" in call_args

    @pytest.mark.asyncio
    async def test_progress_command_displays_level_mastery(
        self, db_session, mock_update, mock_context
    ):
        """Test that progress command displays level mastery."""
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

        # Create 5 progress records to meet mastery threshold (using different tasks)
        for i in range(5):
            progress = Progress(
                user_id=user.telegram_user_id,
                task_id=tasks[i].sheets_row_id,
                answers={},
                score=8.0,
                percentage_correct=80.0,
            )
            db_session.add(progress)

        db_session.commit()

        with patch("src.english_tutor.api.bot.handlers.progress.get_session_local") as mock_session:
            mock_session.return_value = lambda: db_session

            await progress_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Освоение уровней" in call_args or "Level mastery" in call_args
            assert "A1" in call_args

    @pytest.mark.asyncio
    async def test_progress_command_handles_no_data(self, db_session, mock_update, mock_context):
        """Test progress command when user has no progress data."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        with patch("src.english_tutor.api.bot.handlers.progress.get_session_local") as mock_session:
            mock_session.return_value = lambda: db_session

            await progress_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            # Should still display the progress structure, just with zeros/None
            assert "прогресс" in call_args.lower() or "progress" in call_args.lower()

    @pytest.mark.asyncio
    async def test_progress_command_handles_errors(self, db_session, mock_update, mock_context):
        """Test that progress command handles errors gracefully."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        with patch("src.english_tutor.api.bot.handlers.progress.get_session_local") as mock_session:
            mock_session.return_value = lambda: db_session

            # Make ProgressService.calculate_progress raise an exception
            with patch(
                "src.english_tutor.api.bot.handlers.progress.ProgressService.calculate_progress"
            ) as mock_calc:
                mock_calc.side_effect = Exception("Database error")

                await progress_command(mock_update, mock_context)

                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "ошибка" in call_args.lower() or "error" in call_args.lower()

    @pytest.mark.asyncio
    async def test_progress_command_shows_skill_without_data(
        self, db_session, mock_update, mock_context
    ):
        """Test that skills without data show 'Недостаточно данных'."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        with patch("src.english_tutor.api.bot.handlers.progress.get_session_local") as mock_session:
            mock_session.return_value = lambda: db_session

            await progress_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            # Should show "Недостаточно данных" for skills without data
            assert "Недостаточно данных" in call_args or "Not enough data" in call_args

    @pytest.mark.asyncio
    async def test_progress_command_uses_markdown(self, db_session, mock_update, mock_context):
        """Test that progress command uses Markdown formatting."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        with patch("src.english_tutor.api.bot.handlers.progress.get_session_local") as mock_session:
            mock_session.return_value = lambda: db_session

            await progress_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            # Check that parse_mode="Markdown" is passed
            call_kwargs = mock_update.message.reply_text.call_args[1]
            assert call_kwargs.get("parse_mode") == "Markdown"
