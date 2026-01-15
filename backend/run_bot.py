"""Run the Telegram bot locally."""

import asyncio
import signal
import sys

from src.english_tutor.api.bot import start_bot, stop_bot

# Import config first to initialize logging
from src.english_tutor.config import DEBUG  # noqa: F401
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)

# Global flag to track shutdown
_shutdown_event = asyncio.Event()


def _signal_handler() -> None:
    """Handle shutdown signals gracefully."""
    logger.info("Received shutdown signal, initiating graceful shutdown...")
    _shutdown_event.set()


async def main() -> None:
    """Start the bot and keep the event loop alive until shutdown signal."""
    loop = asyncio.get_running_loop()

    # Register signal handlers for graceful shutdown using asyncio
    # This is the recommended way for asyncio applications
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except (ValueError, OSError):
            # Signal handlers can only be registered in the main thread
            # On Windows, some signals may not be available
            logger.debug(f"Could not register signal handler for {sig}")

    try:
        await start_bot()
        logger.info("Bot is running. Press Ctrl+C to stop.")
        # Wait for shutdown signal
        await _shutdown_event.wait()
    except asyncio.CancelledError:
        logger.info("Bot task was cancelled")
    finally:
        logger.info("Shutting down bot...")
        try:
            await stop_bot()
        except Exception as e:
            logger.warning(f"Error during bot shutdown: {e}")
        finally:
            logger.info("Bot shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown complete")
        sys.exit(0)
