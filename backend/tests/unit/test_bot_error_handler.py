"""Unit tests for bot error handler.

Tests for the improved error handler that gracefully handles
expired callback queries and other common Telegram API errors.
"""

# Load bot_module the same way the bot package does
import importlib.util
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from telegram import Update
from telegram.error import BadRequest, NetworkError, RetryAfter, TimedOut

_bot_py_path = Path(__file__).parent.parent.parent / "src" / "english_tutor" / "api" / "bot.py"
spec = importlib.util.spec_from_file_location("bot_module", _bot_py_path)
bot_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot_module)


class TestBotErrorHandler:
    """Test suite for bot error handler."""

    @pytest.fixture
    def mock_update(self):
        """Create a mock Update."""
        update = MagicMock(spec=Update)
        update.update_id = 12345
        update.effective_user = MagicMock()
        update.effective_user.id = 67890
        update.callback_query = None
        return update

    @pytest.fixture
    def mock_context(self):
        """Create a mock Context with error."""
        context = MagicMock()
        return context

    @pytest.mark.asyncio
    async def test_expired_query_too_old_logs_debug(self, mock_update, mock_context):
        """Test that expired query (too old) logs as debug and returns."""
        mock_context.error = BadRequest("Query is too old and response timeout expired")

        with patch.object(bot_module, "logger") as mock_logger:
            await bot_module.handle_error(mock_update, mock_context)

        # Should log as debug, not error
        mock_logger.debug.assert_called_once()
        mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_expired_query_invalid_id_logs_debug(self, mock_update, mock_context):
        """Test that expired query (invalid ID) logs as debug and returns."""
        mock_context.error = BadRequest("query id is invalid")

        with patch.object(bot_module, "logger") as mock_logger:
            await bot_module.handle_error(mock_update, mock_context)

        mock_logger.debug.assert_called_once()
        mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_expired_query_includes_callback_query_id(self, mock_update, mock_context):
        """Test that expired query log includes callback query ID if available."""
        mock_context.error = BadRequest("Query is too old")
        mock_update.callback_query = MagicMock()
        mock_update.callback_query.id = "callback_123"

        with patch.object(bot_module, "logger") as mock_logger:
            await bot_module.handle_error(mock_update, mock_context)

        log_call = mock_logger.debug.call_args
        extra = log_call.kwargs.get("extra", {})
        assert extra.get("callback_query_id") == "callback_123"

    @pytest.mark.asyncio
    async def test_message_not_modified_logs_debug(self, mock_update, mock_context):
        """Test that 'message not modified' error logs as debug and returns."""
        mock_context.error = BadRequest("message is not modified")

        with patch.object(bot_module, "logger") as mock_logger:
            await bot_module.handle_error(mock_update, mock_context)

        mock_logger.debug.assert_called_once()
        mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_network_error_logs_warning(self, mock_update, mock_context):
        """Test that network errors log as warning and return."""
        mock_context.error = NetworkError("Connection timeout")

        with patch.object(bot_module, "logger") as mock_logger:
            await bot_module.handle_error(mock_update, mock_context)

        mock_logger.warning.assert_called_once()
        mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_timeout_error_logs_warning(self, mock_update, mock_context):
        """Test that timeout errors log as warning and return."""
        mock_context.error = TimedOut("Request timed out")

        with patch.object(bot_module, "logger") as mock_logger:
            await bot_module.handle_error(mock_update, mock_context)

        mock_logger.warning.assert_called_once()
        mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_retry_after_logs_warning(self, mock_update, mock_context):
        """Test that rate limiting (RetryAfter) logs as warning and returns."""
        mock_context.error = RetryAfter(retry_after=30)

        with patch.object(bot_module, "logger") as mock_logger:
            await bot_module.handle_error(mock_update, mock_context)

        mock_logger.warning.assert_called_once()
        mock_logger.error.assert_not_called()

        # Verify retry_after is included in log
        # With PTB_TIMEDELTA=1, retry_after is a timedelta, otherwise it's an int
        log_call = mock_logger.warning.call_args
        extra = log_call.kwargs.get("extra", {})
        retry_after_value = extra.get("retry_after")
        # Accept either timedelta or int (timedelta when PTB_TIMEDELTA is set)
        assert retry_after_value == timedelta(seconds=30) or retry_after_value == 30

    @pytest.mark.asyncio
    async def test_other_error_logs_as_system_error(self, mock_update, mock_context):
        """Test that other errors are logged as system errors."""
        mock_context.error = ValueError("Some other error")

        with patch.object(bot_module, "log_system_error") as mock_log_system_error:
            await bot_module.handle_error(mock_update, mock_context)

        mock_log_system_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_bad_request_other_error_logs_as_system_error(self, mock_update, mock_context):
        """Test that other BadRequest errors (not expired queries) log as system errors."""
        mock_context.error = BadRequest("Invalid chat_id")

        with patch.object(bot_module, "log_system_error") as mock_log_system_error:
            await bot_module.handle_error(mock_update, mock_context)

        mock_log_system_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handler_handles_none_update(self, mock_context):
        """Test that error handler handles None update gracefully."""
        mock_context.error = BadRequest("Query is too old")

        with patch.object(bot_module, "logger") as mock_logger:
            await bot_module.handle_error(None, mock_context)

        # Should still log as debug without crashing
        mock_logger.debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handler_handles_none_user(self, mock_context):
        """Test that error handler handles update with None user gracefully."""
        mock_context.error = BadRequest("Query is too old")
        update = MagicMock(spec=Update)
        update.update_id = 12345
        update.effective_user = None
        update.callback_query = None

        with patch.object(bot_module, "logger") as mock_logger:
            await bot_module.handle_error(update, mock_context)

        # Should still log as debug without crashing
        mock_logger.debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handler_case_insensitive_error_matching(self, mock_update, mock_context):
        """Test that error message matching is case-insensitive."""
        mock_context.error = BadRequest("QUERY IS TOO OLD AND RESPONSE TIMEOUT EXPIRED")

        with patch.object(bot_module, "logger") as mock_logger:
            await bot_module.handle_error(mock_update, mock_context)

        mock_logger.debug.assert_called_once()
        mock_logger.error.assert_not_called()
