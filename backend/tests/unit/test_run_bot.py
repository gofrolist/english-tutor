"""Unit tests for bot runner script.

Tests that verify the bot can be imported and started correctly.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.english_tutor.api.bot import start_bot


class TestBotRunner:
    """Test suite for bot runner functionality."""

    @pytest.mark.asyncio
    async def test_start_bot_can_be_imported(self):
        """Test that start_bot can be imported from bot package."""
        # This test verifies the import works (fixes the naming conflict issue)
        assert callable(start_bot)

    @pytest.mark.asyncio
    async def test_start_bot_initializes_and_starts(self):
        """Test that start_bot initializes and starts the bot application."""
        # Patch at the module level where start_bot is actually defined
        with patch("src.english_tutor.api.bot.bot_module.get_bot_application") as mock_get_app:
            mock_app = AsyncMock()
            mock_get_app.return_value = mock_app

            await start_bot()

            # Verify bot application was retrieved
            mock_get_app.assert_called_once()

            # Verify initialization sequence
            mock_app.initialize.assert_called_once()
            mock_app.start.assert_called_once()
            mock_app.updater.start_polling.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_bot_script_imports_correctly(self):
        """Test that run_bot.py can import start_bot correctly."""
        # This test verifies the import path works from the script's perspective
        from src.english_tutor.api.bot import start_bot as imported_start_bot

        assert callable(imported_start_bot)

    def test_bot_package_exports_start_bot(self):
        """Test that bot package __init__.py exports start_bot."""
        # Verify the package re-exports the function
        from src.english_tutor.api.bot import (
            get_bot_application,
            start_bot,
            stop_bot,
        )

        assert callable(start_bot)
        assert callable(stop_bot)
        assert callable(get_bot_application)
