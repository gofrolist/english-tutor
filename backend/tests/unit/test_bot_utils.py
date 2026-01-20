"""Unit tests for Telegram bot utility functions.

Tests for safe callback query handling and message editing utilities
that gracefully handle expired queries.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import CallbackQuery, Message
from telegram import User as TelegramUser
from telegram.error import BadRequest

from src.english_tutor.api.bot.utils import safe_answer_callback_query, safe_edit_message_text


class TestSafeAnswerCallbackQuery:
    """Test suite for safe_answer_callback_query utility."""

    @pytest.fixture
    def mock_query(self):
        """Create a mock CallbackQuery."""
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.id = "test_query_id"
        query.from_user = MagicMock(spec=TelegramUser)
        query.from_user.id = 12345
        query.data = "test_callback_data"
        return query

    @pytest.mark.asyncio
    async def test_successful_answer(self, mock_query):
        """Test that successful query answer returns True."""
        mock_query.answer.return_value = True

        result = await safe_answer_callback_query(mock_query)

        assert result is True
        mock_query.answer.assert_called_once_with(text=None, show_alert=False)

    @pytest.mark.asyncio
    async def test_successful_answer_with_text(self, mock_query):
        """Test that successful query answer with text returns True."""
        mock_query.answer.return_value = True

        result = await safe_answer_callback_query(mock_query, text="Test message")

        assert result is True
        mock_query.answer.assert_called_once_with(text="Test message", show_alert=False)

    @pytest.mark.asyncio
    async def test_successful_answer_with_alert(self, mock_query):
        """Test that successful query answer with alert returns True."""
        mock_query.answer.return_value = True

        result = await safe_answer_callback_query(mock_query, text="Alert", show_alert=True)

        assert result is True
        mock_query.answer.assert_called_once_with(text="Alert", show_alert=True)

    @pytest.mark.asyncio
    async def test_expired_query_too_old(self, mock_query):
        """Test that expired query (too old) returns False and doesn't raise."""
        mock_query.answer.side_effect = BadRequest("Query is too old and response timeout expired")

        with patch("src.english_tutor.api.bot.utils.logger") as mock_logger:
            result = await safe_answer_callback_query(mock_query)

        assert result is False
        mock_query.answer.assert_called_once()
        # Verify warning was logged
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_expired_query_invalid_id(self, mock_query):
        """Test that expired query (invalid ID) returns False and doesn't raise."""
        mock_query.answer.side_effect = BadRequest("query id is invalid")

        with patch("src.english_tutor.api.bot.utils.logger") as mock_logger:
            result = await safe_answer_callback_query(mock_query)

        assert result is False
        mock_query.answer.assert_called_once()
        # Verify warning was logged
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_expired_query_case_insensitive(self, mock_query):
        """Test that expired query detection is case-insensitive."""
        mock_query.answer.side_effect = BadRequest("QUERY IS TOO OLD AND RESPONSE TIMEOUT EXPIRED")

        with patch("src.english_tutor.api.bot.utils.logger") as mock_logger:
            result = await safe_answer_callback_query(mock_query)

        assert result is False
        mock_query.answer.assert_called_once()
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_other_bad_request_raises(self, mock_query):
        """Test that other BadRequest errors are re-raised."""
        mock_query.answer.side_effect = BadRequest("Invalid parameter")

        with pytest.raises(BadRequest) as exc_info:
            await safe_answer_callback_query(mock_query)

        assert "Invalid parameter" in str(exc_info.value)
        mock_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_none_query_returns_false(self):
        """Test that None query returns False."""
        result = await safe_answer_callback_query(None)

        assert result is False

    @pytest.mark.asyncio
    async def test_logs_expired_query_details(self, mock_query):
        """Test that expired query logs include query details."""
        mock_query.answer.side_effect = BadRequest("Query is too old and response timeout expired")

        with patch("src.english_tutor.api.bot.utils.logger") as mock_logger:
            await safe_answer_callback_query(mock_query)

        # Verify log call includes query details
        log_call = mock_logger.warning.call_args
        assert log_call is not None
        extra = log_call.kwargs.get("extra", {})
        assert extra.get("query_id") == "test_query_id"
        assert extra.get("user_id") == 12345
        assert extra.get("callback_data") == "test_callback_data"


class TestSafeEditMessageText:
    """Test suite for safe_edit_message_text utility."""

    @pytest.fixture
    def mock_query(self):
        """Create a mock CallbackQuery with a message."""
        query = MagicMock(spec=CallbackQuery)
        query.edit_message_text = AsyncMock()
        query.message = MagicMock(spec=Message)
        query.message.reply_text = AsyncMock()
        query.id = "test_query_id"
        query.from_user = MagicMock(spec=TelegramUser)
        query.from_user.id = 12345
        query.data = "test_callback_data"
        return query

    @pytest.mark.asyncio
    async def test_successful_edit(self, mock_query):
        """Test that successful message edit returns True."""
        mock_query.edit_message_text.return_value = True

        result = await safe_edit_message_text(mock_query, "Test message")

        assert result is True
        mock_query.edit_message_text.assert_called_once_with("Test message")
        mock_query.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_edit_with_kwargs(self, mock_query):
        """Test that successful message edit with kwargs returns True."""
        mock_query.edit_message_text.return_value = True

        result = await safe_edit_message_text(mock_query, "Test message", parse_mode="Markdown")

        assert result is True
        mock_query.edit_message_text.assert_called_once_with("Test message", parse_mode="Markdown")

    @pytest.mark.asyncio
    async def test_expired_query_fallback_to_reply(self, mock_query):
        """Test that expired query falls back to sending new message."""
        mock_query.edit_message_text.side_effect = BadRequest(
            "Query is too old and response timeout expired"
        )
        mock_query.message.reply_text.return_value = MagicMock()

        with patch("src.english_tutor.api.bot.utils.logger") as mock_logger:
            result = await safe_edit_message_text(mock_query, "Test message")

        assert result is True
        mock_query.edit_message_text.assert_called_once()
        # Verify fallback to reply_text was used
        mock_query.message.reply_text.assert_called_once_with("Test message")
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_query_id_fallback(self, mock_query):
        """Test that invalid query ID falls back to sending new message."""
        mock_query.edit_message_text.side_effect = BadRequest("query id is invalid")
        mock_query.message.reply_text.return_value = MagicMock()

        with patch("src.english_tutor.api.bot.utils.logger") as mock_logger:
            result = await safe_edit_message_text(mock_query, "Test message")

        assert result is True
        mock_query.message.reply_text.assert_called_once()
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_message_not_modified_fallback(self, mock_query):
        """Test that 'message not modified' error falls back to sending new message."""
        mock_query.edit_message_text.side_effect = BadRequest("message is not modified")
        mock_query.message.reply_text.return_value = MagicMock()

        with patch("src.english_tutor.api.bot.utils.logger") as mock_logger:
            result = await safe_edit_message_text(mock_query, "Test message")

        assert result is True
        mock_query.message.reply_text.assert_called_once()
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_message_not_found_fallback(self, mock_query):
        """Test that 'message not found' error falls back to sending new message."""
        mock_query.edit_message_text.side_effect = BadRequest("message to edit not found")
        mock_query.message.reply_text.return_value = MagicMock()

        with patch("src.english_tutor.api.bot.utils.logger") as mock_logger:
            result = await safe_edit_message_text(mock_query, "Test message")

        assert result is True
        mock_query.message.reply_text.assert_called_once()
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_preserves_kwargs(self, mock_query):
        """Test that fallback to reply_text preserves kwargs."""
        mock_query.edit_message_text.side_effect = BadRequest("Query is too old")
        mock_query.message.reply_text.return_value = MagicMock()

        result = await safe_edit_message_text(
            mock_query, "Test message", parse_mode="Markdown", reply_markup=MagicMock()
        )

        assert result is True
        mock_query.message.reply_text.assert_called_once()
        call_kwargs = mock_query.message.reply_text.call_args[1]
        assert call_kwargs.get("parse_mode") == "Markdown"
        assert "reply_markup" in call_kwargs

    @pytest.mark.asyncio
    async def test_fallback_reply_failure_returns_false(self, mock_query):
        """Test that if fallback reply_text also fails, returns False."""
        mock_query.edit_message_text.side_effect = BadRequest("Query is too old")
        mock_query.message.reply_text.side_effect = Exception("Network error")

        with patch("src.english_tutor.api.bot.utils.logger") as mock_logger:
            result = await safe_edit_message_text(mock_query, "Test message")

        assert result is False
        # Should have logged both warnings
        assert mock_logger.warning.call_count >= 1
        # Should have logged error for fallback failure
        mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_other_bad_request_raises(self, mock_query):
        """Test that other BadRequest errors are re-raised."""
        mock_query.edit_message_text.side_effect = BadRequest("Invalid parameter")

        with pytest.raises(BadRequest) as exc_info:
            await safe_edit_message_text(mock_query, "Test message")

        assert "Invalid parameter" in str(exc_info.value)
        mock_query.edit_message_text.assert_called_once()
        mock_query.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_query_returns_false(self):
        """Test that None query returns False."""
        result = await safe_edit_message_text(None, "Test message")

        assert result is False

    @pytest.mark.asyncio
    async def test_none_message_returns_false(self):
        """Test that query with None message returns False."""
        query = MagicMock(spec=CallbackQuery)
        query.message = None

        result = await safe_edit_message_text(query, "Test message")

        assert result is False
