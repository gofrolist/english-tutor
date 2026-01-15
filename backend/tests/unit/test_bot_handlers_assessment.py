"""Unit tests for assessment bot handlers.

Tests for Telegram bot handlers in the assessment flow, including
callback query handling that was previously buggy.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from telegram import CallbackQuery, Message, Update
from telegram import User as TelegramUser

from src.english_tutor.api.bot.handlers.assessment import (
    assess_command,
    handle_assessment_answer,
    send_assessment_question,
)
from src.english_tutor.models.assessment import Assessment, AssessmentStatus
from src.english_tutor.models.assessment_question import AssessmentQuestion
from src.english_tutor.models.user import User


class TestAssessmentHandlers:
    """Test suite for assessment bot handlers."""

    @pytest.fixture
    def mock_update_message(self):
        """Create a mock Update with a Message."""
        update = MagicMock(spec=Update)
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        update.message.reply_text.return_value = MagicMock()
        update.effective_user = MagicMock(spec=TelegramUser)
        update.effective_user.id = 12345
        update.callback_query = None
        return update

    @pytest.fixture
    def mock_update_callback_query(self):
        """Create a mock Update with a CallbackQuery (no message)."""
        update = MagicMock(spec=Update)
        update.message = None  # This is the key - callback queries don't have message
        update.callback_query = MagicMock(spec=CallbackQuery)
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.message = MagicMock(spec=Message)
        update.callback_query.message.reply_text = AsyncMock()
        update.callback_query.data = "answer_0_1"
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
    async def test_send_assessment_question_with_message(
        self, db_session, mock_update_message, mock_context
    ):
        """Test send_assessment_question works with regular message update."""
        # Create test data
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        question = AssessmentQuestion(
            level="A1",
            question_text="Test question?",
            answer_options=["Option 1", "Option 2"],
            correct_answer=0,
            weight=1.0,
        )
        db_session.add(question)
        db_session.commit()

        assessment = Assessment(
            user_id=user.id,
            questions=[str(question.id)],
            answers={},
            score=0.0,
            status=AssessmentStatus.IN_PROGRESS,
        )
        db_session.add(assessment)
        db_session.commit()

        # Set context
        mock_context.user_data["current_question_index"] = 0

        # Call function
        await send_assessment_question(mock_update_message, mock_context, assessment.id, db_session)

        # Verify message was sent
        mock_update_message.message.reply_text.assert_called_once()
        call_args = mock_update_message.message.reply_text.call_args
        assert "Вопрос 1/1" in call_args[0][0]
        assert "Test question?" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_send_assessment_question_with_callback_query(
        self, db_session, mock_update_callback_query, mock_context
    ):
        """Test send_assessment_question works with callback query update (the bug fix)."""
        # This test specifically covers the bug where update.message was None
        # Create test data
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        question = AssessmentQuestion(
            level="A1",
            question_text="Test question?",
            answer_options=["Option 1", "Option 2"],
            correct_answer=0,
            weight=1.0,
        )
        db_session.add(question)
        db_session.commit()

        assessment = Assessment(
            user_id=user.id,
            questions=[str(question.id)],
            answers={},
            score=0.0,
            status=AssessmentStatus.IN_PROGRESS,
        )
        db_session.add(assessment)
        db_session.commit()

        # Set context
        mock_context.user_data["current_question_index"] = 0

        # Call function - this should NOT raise AttributeError
        await send_assessment_question(
            mock_update_callback_query, mock_context, assessment.id, db_session
        )

        # Verify message was sent via callback_query.message
        mock_update_callback_query.callback_query.message.reply_text.assert_called_once()
        call_args = mock_update_callback_query.callback_query.message.reply_text.call_args
        assert "Вопрос 1/1" in call_args[0][0]
        assert "Test question?" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_assessment_answer_sends_next_question(
        self, db_session, mock_update_callback_query, mock_context
    ):
        """Test that handle_assessment_answer sends next question via callback query."""
        # Create test data
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        question1 = AssessmentQuestion(
            level="A1",
            question_text="Question 1?",
            answer_options=["A", "B"],
            correct_answer=0,
            weight=1.0,
        )
        question2 = AssessmentQuestion(
            level="A1",
            question_text="Question 2?",
            answer_options=["C", "D"],
            correct_answer=1,
            weight=1.0,
        )
        db_session.add_all([question1, question2])
        db_session.commit()

        assessment = Assessment(
            user_id=user.id,
            questions=[str(question1.id), str(question2.id)],
            answers={},
            score=0.0,
            status=AssessmentStatus.IN_PROGRESS,
        )
        db_session.add(assessment)
        db_session.commit()

        # Store IDs before handler closes session
        assessment_id = assessment.id
        question1_id = question1.id

        # Set context
        mock_context.user_data["current_assessment_id"] = str(assessment_id)
        mock_context.user_data["current_question_index"] = 0

        # Mock the callback query data
        mock_update_callback_query.callback_query.data = "answer_0_1"

        # Mock get_session_local to return our test session
        with patch(
            "src.english_tutor.api.bot.handlers.assessment.get_session_local",
            return_value=self._mock_session_local(db_session),
        ):
            # Call function
            await handle_assessment_answer(mock_update_callback_query, mock_context)

        # Verify answer was called (called twice: once at start, once with message)
        assert mock_update_callback_query.callback_query.answer.call_count >= 1

        # Verify next question was sent via callback_query.message.reply_text
        # (since update.message is None in callback queries)
        mock_update_callback_query.callback_query.message.reply_text.assert_called_once()
        call_args = mock_update_callback_query.callback_query.message.reply_text.call_args
        assert "Вопрос 2/2" in call_args[0][0]
        assert "Question 2?" in call_args[0][0]

        # Verify answer was stored (query fresh from DB since handler closed its session)
        updated_assessment = (
            db_session.query(Assessment).filter(Assessment.id == assessment_id).first()
        )
        assert str(question1_id) in updated_assessment.answers
        assert updated_assessment.answers[str(question1_id)] == 1

    @pytest.mark.asyncio
    async def test_handle_assessment_answer_completes_assessment_on_last_question(
        self, db_session, mock_update_callback_query, mock_context
    ):
        """Test that handle_assessment_answer completes assessment on last question."""
        # Create test data
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        question = AssessmentQuestion(
            level="A1",
            question_text="Question 1?",
            answer_options=["A", "B"],
            correct_answer=0,
            weight=1.0,
        )
        db_session.add(question)
        db_session.commit()

        assessment = Assessment(
            user_id=user.id,
            questions=[str(question.id)],
            answers={},
            score=0.0,
            status=AssessmentStatus.IN_PROGRESS,
        )
        db_session.add(assessment)
        db_session.commit()

        # Set context
        mock_context.user_data["current_assessment_id"] = str(assessment.id)
        mock_context.user_data["current_question_index"] = 0

        # Mock the callback query data
        mock_update_callback_query.callback_query.data = "answer_0_1"

        # Mock get_session_local to return our test session
        with patch(
            "src.english_tutor.api.bot.handlers.assessment.get_session_local",
            return_value=self._mock_session_local(db_session),
        ):
            # Mock complete_and_deliver_result to avoid full completion flow
            with patch(
                "src.english_tutor.api.bot.handlers.assessment.complete_and_deliver_result"
            ) as mock_complete:
                mock_complete.return_value = AsyncMock()
                # Call function
                await handle_assessment_answer(mock_update_callback_query, mock_context)

        # Verify complete_and_deliver_result was called
        mock_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_assessment_answer_handles_invalid_user(
        self, db_session, mock_update_callback_query, mock_context
    ):
        """Test that handle_assessment_answer handles missing user gracefully."""
        # User doesn't exist
        mock_context.user_data["current_assessment_id"] = str(uuid4())
        mock_update_callback_query.callback_query.data = "answer_0_1"

        with patch(
            "src.english_tutor.api.bot.handlers.assessment.get_session_local",
            return_value=self._mock_session_local(db_session),
        ):
            await handle_assessment_answer(mock_update_callback_query, mock_context)

        # Verify error message was sent
        mock_update_callback_query.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update_callback_query.callback_query.edit_message_text.call_args
        assert "Пользователь не найден" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_assessment_answer_handles_missing_assessment_id(
        self, db_session, mock_update_callback_query, mock_context
    ):
        """Test that handle_assessment_answer handles missing assessment ID."""
        # Create user but no assessment ID in context
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        mock_context.user_data = {}  # No assessment ID
        mock_update_callback_query.callback_query.data = "answer_0_1"

        with patch(
            "src.english_tutor.api.bot.handlers.assessment.get_session_local",
            return_value=self._mock_session_local(db_session),
        ):
            await handle_assessment_answer(mock_update_callback_query, mock_context)

        # Verify error message was sent
        mock_update_callback_query.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update_callback_query.callback_query.edit_message_text.call_args
        assert "Активная оценка не найдена" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_assess_command_requires_user_to_exist(
        self, db_session, mock_update_message, mock_context
    ):
        """Test that assess_command requires user to exist (created via /start)."""
        # User doesn't exist yet

        # Mock get_session_local to return our test session
        with patch(
            "src.english_tutor.api.bot.handlers.assessment.get_session_local",
            return_value=self._mock_session_local(db_session),
        ):
            # Call function
            await assess_command(mock_update_message, mock_context)

        # Verify error message was sent
        mock_update_message.message.reply_text.assert_called_once()
        call_args = mock_update_message.message.reply_text.call_args
        assert "Пожалуйста, сначала запустите бота командой /start" in call_args[0][0]

        # Verify user was NOT created
        user = db_session.query(User).filter(User.telegram_user_id == "12345").first()
        assert user is None

    @pytest.mark.asyncio
    async def test_assess_command_abandons_existing_assessment(
        self, db_session, mock_update_message, mock_context
    ):
        """Test that assess_command abandons existing in-progress assessment."""
        # Create user with existing assessment
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        old_assessment = Assessment(
            user_id=user.id,
            questions=["q1"],
            answers={},
            score=0.0,
            status=AssessmentStatus.IN_PROGRESS,
        )
        db_session.add(old_assessment)
        db_session.commit()

        # Create a question for the new assessment
        question = AssessmentQuestion(
            level="A1",
            question_text="Test?",
            answer_options=["A", "B"],
            correct_answer=0,
            weight=1.0,
        )
        db_session.add(question)
        db_session.commit()

        # Store IDs before handler closes session
        old_assessment_id = old_assessment.id
        user_id = user.id

        # Mock get_session_local to return our test session
        with patch(
            "src.english_tutor.api.bot.handlers.assessment.get_session_local",
            return_value=self._mock_session_local(db_session),
        ):
            # Call function
            await assess_command(mock_update_message, mock_context)

        # Verify old assessment was abandoned (query fresh from DB since handler closed its session)
        abandoned_assessment = (
            db_session.query(Assessment).filter(Assessment.id == old_assessment_id).first()
        )
        assert abandoned_assessment is not None
        assert abandoned_assessment.status == AssessmentStatus.ABANDONED

        # Verify new assessment was created
        new_assessments = (
            db_session.query(Assessment)
            .filter(
                Assessment.user_id == user_id, Assessment.status == AssessmentStatus.IN_PROGRESS
            )
            .all()
        )
        assert len(new_assessments) == 1
        assert new_assessments[0].id != old_assessment_id

    @pytest.mark.asyncio
    async def test_assess_command_with_existing_user(
        self, db_session, mock_update_message, mock_context
    ):
        """Test that assess_command works when user exists."""
        # Create user first
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        # Create a question for the assessment
        question = AssessmentQuestion(
            level="A1",
            question_text="Test?",
            answer_options=["A", "B"],
            correct_answer=0,
            weight=1.0,
        )
        db_session.add(question)
        db_session.commit()

        # Mock get_session_local to return our test session
        with patch(
            "src.english_tutor.api.bot.handlers.assessment.get_session_local",
            return_value=self._mock_session_local(db_session),
        ):
            # Call function
            await assess_command(mock_update_message, mock_context)

        # Verify assessment was started (message was sent)
        assert mock_update_message.message.reply_text.call_count >= 1

    @pytest.mark.asyncio
    async def test_send_assessment_question_completes_when_all_answered(
        self, db_session, mock_update_message, mock_context
    ):
        """Test that send_assessment_question completes assessment when all questions answered."""
        # Create test data
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        assessment = Assessment(
            user_id=user.id,
            questions=[],  # No questions
            answers={},
            score=0.0,
            status=AssessmentStatus.IN_PROGRESS,
        )
        db_session.add(assessment)
        db_session.commit()

        # Set context to indicate all questions answered
        mock_context.user_data["current_question_index"] = 1  # Beyond question list

        # Mock complete_and_deliver_result
        with patch(
            "src.english_tutor.api.bot.handlers.assessment.complete_and_deliver_result"
        ) as mock_complete:
            mock_complete.return_value = AsyncMock()
            await send_assessment_question(
                mock_update_message, mock_context, assessment.id, db_session
            )

        # Verify completion was triggered
        mock_complete.assert_called_once()
