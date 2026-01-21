"""Unit tests for assessment handler silent failure scenarios.

Tests to catch scenarios where the bot might stop responding without logging errors.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from telegram import CallbackQuery, Update
from telegram import User as TelegramUser

from src.english_tutor.api.bot.handlers.assessment import handle_assessment_answer
from src.english_tutor.models.assessment import Assessment, AssessmentStatus
from src.english_tutor.models.assessment_question import AssessmentQuestion
from src.english_tutor.models.user import User


class TestAssessmentHandlerSilentFailures:
    """Test suite for catching silent failures in assessment handler."""

    @pytest.fixture
    def mock_update_callback_query(self):
        """Create a mock Update with a CallbackQuery."""
        update = MagicMock(spec=Update)
        update.message = None
        update.callback_query = MagicMock(spec=CallbackQuery)
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.message = MagicMock()
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
    async def test_handler_logs_error_on_database_commit_failure(
        self, db_session, mock_update_callback_query, mock_context
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
            user_id=user.id,
            questions=[str(question.id)],
            answers={},
            score=0.0,
            status=AssessmentStatus.IN_PROGRESS,
        )
        db_session.add(assessment)
        db_session.commit()

        assessment_id = assessment.id
        mock_context.user_data["current_assessment_id"] = str(assessment_id)
        mock_update_callback_query.callback_query.data = "answer_0_1"

        # Mock db.commit() to raise an exception
        with patch.object(db_session, "commit", side_effect=Exception("Database error")):
            with patch(
                "src.english_tutor.api.bot.handlers.assessment.get_session_local",
                return_value=self._mock_session_local(db_session),
            ):
                with patch("src.english_tutor.api.bot.handlers.assessment.logger") as mock_logger:
                    # Exception should be caught and logged, then re-raised
                    with pytest.raises(Exception):
                        await handle_assessment_answer(mock_update_callback_query, mock_context)

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
    async def test_handler_logs_error_on_invalid_callback_data(
        self, db_session, mock_update_callback_query, mock_context
    ):
        """Test that handler logs error when callback data is invalid."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        # Set invalid callback data
        mock_update_callback_query.callback_query.data = "invalid_format"
        mock_context.user_data = {}

        with patch(
            "src.english_tutor.api.bot.handlers.assessment.get_session_local",
            return_value=self._mock_session_local(db_session),
        ):
            with patch("src.english_tutor.api.bot.handlers.assessment.logger") as mock_logger:
                # Handler should not crash silently, even with invalid data
                await handle_assessment_answer(mock_update_callback_query, mock_context)

                # Handler should have tried to send an error message
                # (either via edit_message_text or error logging)
                assert (
                    mock_update_callback_query.callback_query.edit_message_text.called
                    or mock_logger.error.called
                )

    @pytest.mark.asyncio
    async def test_handler_handles_missing_assessment_gracefully(
        self, db_session, mock_update_callback_query, mock_context
    ):
        """Test that handler handles missing assessment without crashing."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        # Set assessment ID that doesn't exist
        mock_context.user_data["current_assessment_id"] = str(uuid4())
        mock_update_callback_query.callback_query.data = "answer_0_1"

        with patch(
            "src.english_tutor.api.bot.handlers.assessment.get_session_local",
            return_value=self._mock_session_local(db_session),
        ):
            # Should not raise exception
            await handle_assessment_answer(mock_update_callback_query, mock_context)

            # Should try to send error message
            mock_update_callback_query.callback_query.edit_message_text.assert_called()

    @pytest.mark.asyncio
    async def test_handler_handles_network_error_during_message_send(
        self, db_session, mock_update_callback_query, mock_context
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
            user_id=user.id,
            questions=[str(question1.id), str(question2.id)],
            answers={},
            score=0.0,
            status=AssessmentStatus.IN_PROGRESS,
        )
        db_session.add(assessment)
        db_session.commit()

        assessment_id = assessment.id
        mock_context.user_data["current_assessment_id"] = str(assessment_id)
        mock_context.user_data["current_question_index"] = 0
        mock_update_callback_query.callback_query.data = "answer_0_1"

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
                        await handle_assessment_answer(mock_update_callback_query, mock_context)

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
        self, db_session, mock_update_callback_query, mock_context
    ):
        """Test that database session is always closed even if exception occurs."""
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        mock_update_callback_query.callback_query.data = "answer_0_1"
        mock_context.user_data["current_assessment_id"] = str(uuid4())

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
                await handle_assessment_answer(mock_update_callback_query, mock_context)

            # Verify db.close was called
            assert db_close_called
        finally:
            if hasattr(db_session, "close"):
                db_session.close = original_close
