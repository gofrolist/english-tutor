"""Unit tests for assessment handler silent failure scenarios.

Tests to catch scenarios where the bot might stop responding without logging errors.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from telegram import Message, Update
from telegram import User as TelegramUser

from src.english_tutor.api.bot.handlers.assessment import handle_assessment_answer
from src.english_tutor.models.assessment import Assessment, AssessmentStatus
from src.english_tutor.models.assessment_question import AssessmentQuestion
from src.english_tutor.models.user import User


class TestAssessmentHandlerSilentFailures:
    """Test suite for catching silent failures in assessment handler."""

    @pytest.fixture
    def mock_update_message_with_text(self):
        """Create a mock Update with a Message containing text (for reply keyboard answers)."""
        update = MagicMock(spec=Update)
        update.message = MagicMock(spec=Message)
        update.message.text = "Option 1"  # Default answer text
        update.message.reply_text = AsyncMock()
        update.message.reply_text.return_value = MagicMock()
        type(update).effective_message = property(lambda self: self.message)
        update.effective_user = MagicMock(spec=TelegramUser)
        update.effective_user.id = 12345
        update.callback_query = None
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
    @pytest.mark.asyncio
    async def test_handler_logs_error_on_database_commit_failure(
        self, db_session, mock_update_message_with_text, mock_context
    ):
        """Test that handler logs error when database commit fails."""
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
            sheets_row_id="test-row-001",
        )
        db_session.add(question)
        db_session.commit()

        assessment = Assessment(
            sheets_row_id="assessment_1",
            user_id=user.telegram_user_id,
            questions=[question.sheets_row_id],
            answers={},
            score=0.0,
            status=AssessmentStatus.IN_PROGRESS,
        )
        db_session.add(assessment)
        db_session.commit()

        assessment_id = assessment.sheets_row_id
        mock_context.user_data["current_assessment_id"] = assessment_id
        mock_context.user_data["current_question_index"] = 0
        mock_context.user_data["current_question_options"] = question.answer_options
        mock_update_message_with_text.message.text = "Option 1"

        # Mock db.commit() to raise an exception
        with patch.object(db_session, "commit", side_effect=Exception("Database error")):
            with patch(
                "src.english_tutor.api.bot.handlers.assessment.get_session_local",
                return_value=self._mock_session_local(db_session),
            ):
                with patch("src.english_tutor.api.bot.handlers.assessment.logger") as mock_logger:
                    # Exception should be caught and logged, then re-raised
                    with pytest.raises(Exception):
                        await handle_assessment_answer(mock_update_message_with_text, mock_context)

                    # Verify error was logged
                    mock_logger.error.assert_called()
                    error_calls = [
                        call
                        for call in mock_logger.error.call_args_list
                        if any(
                            keyword in str(call)
                            for keyword in [
                                "Failed to commit answer to database",
                                "Unexpected error",
                            ]
                        )
                    ]
                    assert len(error_calls) > 0

    @pytest.mark.asyncio
    async def test_handler_logs_error_on_invalid_answer_text(
        self, db_session, mock_update_message_with_text, mock_context
    ):
        """Test that handler handles invalid answer text (not matching options)."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        question = AssessmentQuestion(
            level="A1",
            question_text="Test question?",
            answer_options=["Option 1", "Option 2"],
            correct_answer=0,
            weight=1.0,
            sheets_row_id="test-row-001",
        )
        db_session.add(question)
        db_session.commit()

        assessment = Assessment(
            sheets_row_id="assessment_1",
            user_id=user.telegram_user_id,
            questions=[question.sheets_row_id],
            answers={},
            score=0.0,
            status=AssessmentStatus.IN_PROGRESS,
        )
        db_session.add(assessment)
        db_session.commit()

        # Set context with question options
        mock_context.user_data["current_assessment_id"] = assessment.sheets_row_id
        mock_context.user_data["current_question_index"] = 0
        mock_context.user_data["current_question_options"] = question.answer_options

        # Set invalid answer text (doesn't match any option)
        mock_update_message_with_text.message.text = "Invalid Answer"

        with patch(
            "src.english_tutor.api.bot.handlers.assessment.get_session_local",
            return_value=self._mock_session_local(db_session),
        ):
            # Handler should not crash silently, should show error and keep keyboard
            await handle_assessment_answer(mock_update_message_with_text, mock_context)

            # Handler should have sent an error message with keyboard
            assert mock_update_message_with_text.message.reply_text.called
            call_args = mock_update_message_with_text.message.reply_text.call_args
            assert "Пожалуйста, выберите один из предложенных вариантов" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handler_handles_missing_assessment_gracefully(
        self, db_session, mock_update_message_with_text, mock_context
    ):
        """Test that handler handles missing assessment without crashing."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        # Set assessment ID that doesn't exist
        mock_context.user_data["current_assessment_id"] = str(uuid4())
        mock_context.user_data["current_question_index"] = 0
        mock_context.user_data["current_question_options"] = ["Option 1", "Option 2"]
        mock_update_message_with_text.message.text = "Option 1"

        with patch(
            "src.english_tutor.api.bot.handlers.assessment.get_session_local",
            return_value=self._mock_session_local(db_session),
        ):
            # Should not raise exception
            await handle_assessment_answer(mock_update_message_with_text, mock_context)

            # Should try to send error message
            mock_update_message_with_text.message.reply_text.assert_called()
            call_args = mock_update_message_with_text.message.reply_text.call_args
            assert "Оценка не найдена" in call_args[0][0] or "не найдена" in call_args[0][0]

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_handler_handles_network_error_during_message_send(
        self, db_session, mock_update_message_with_text, mock_context
    ):
        """Test that handler logs error when network fails during message send."""
        from telegram.error import NetworkError

        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        question1 = AssessmentQuestion(
            level="A1",
            question_text="Test question 1?",
            answer_options=["Option 1", "Option 2"],
            correct_answer=0,
            weight=1.0,
            sheets_row_id="test-row-002",
        )
        question2 = AssessmentQuestion(
            level="A1",
            question_text="Test question 2?",
            answer_options=["Option 1", "Option 2"],
            correct_answer=0,
            weight=1.0,
            sheets_row_id="test-row-003",
        )
        db_session.add_all([question1, question2])
        db_session.commit()

        assessment = Assessment(
            sheets_row_id="assessment_2",
            user_id=user.telegram_user_id,
            questions=[question1.sheets_row_id, question2.sheets_row_id],
            answers={},
            score=0.0,
            status=AssessmentStatus.IN_PROGRESS,
        )
        db_session.add(assessment)
        db_session.commit()

        assessment_id = assessment.sheets_row_id
        mock_context.user_data["current_assessment_id"] = assessment_id
        mock_context.user_data["current_question_index"] = 0
        mock_context.user_data["current_question_options"] = question1.answer_options
        mock_update_message_with_text.message.text = "Option 1"

        # Mock send_assessment_question to raise NetworkError
        with patch(
            "src.english_tutor.api.bot.handlers.assessment.get_session_local",
            return_value=self._mock_session_local(db_session),
        ):
            with patch(
                "src.english_tutor.api.bot.handlers.assessment.send_assessment_question",
                side_effect=NetworkError("Connection failed"),
            ):
                with patch("src.english_tutor.api.bot.handlers.assessment.logger") as mock_logger:
                    # Exception should be caught and logged, then re-raised
                    with pytest.raises(NetworkError):
                        await handle_assessment_answer(mock_update_message_with_text, mock_context)

                    # Verify error was logged
                    mock_logger.error.assert_called()
                    error_calls = [
                        call
                        for call in mock_logger.error.call_args_list
                        if "Unexpected error" in str(call)
                    ]
                    assert len(error_calls) > 0

    @pytest.mark.asyncio
    async def test_handler_always_closes_database_session(
        self, db_session, mock_update_message_with_text, mock_context
    ):
        """Test that database session is always closed even if exception occurs."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        mock_update_message_with_text.message.text = "Option 1"
        mock_context.user_data["current_assessment_id"] = str(uuid4())
        mock_context.user_data["current_question_index"] = 0
        mock_context.user_data["current_question_options"] = ["Option 1", "Option 2"]

        # Track if close was called
        db_close_called = False
        original_close = db_session.close

        def track_close():
            nonlocal db_close_called
            db_close_called = True
            original_close()

        db_session.close = track_close

        try:
            with patch(
                "src.english_tutor.api.bot.handlers.assessment.get_session_local",
                return_value=self._mock_session_local(db_session),
            ):
                await handle_assessment_answer(mock_update_message_with_text, mock_context)

            # Verify db.close was called
            assert db_close_called
        finally:
            if hasattr(db_session, "close"):
                db_session.close = original_close
