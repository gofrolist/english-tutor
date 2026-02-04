"""Standalone scheduler module for content synchronization.

This module provides a standalone entry point for the content sync scheduler
that can be run independently via 'python -m english_tutor.scheduler'.

Example:
    # Run as module
    python -m english_tutor.scheduler

    # Or import and call directly
    from src.english_tutor.scheduler import run_scheduler
    run_scheduler()
"""

import asyncio
import signal
import sys

# Import config first to initialize logging
from src.english_tutor.config import get_settings  # noqa: F401
from src.english_tutor.services.scheduler import (
    get_scheduler,
    start_scheduler,
    stop_scheduler,
)
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)

# Global flag to track shutdown
_shutdown_event = asyncio.Event()


def _signal_handler() -> None:
    """Handle shutdown signals gracefully."""
    logger.info("Received shutdown signal, initiating graceful shutdown...")
    _shutdown_event.set()


async def _run_scheduler_async() -> None:
    """Run the scheduler with proper async event loop integration.

    This function starts the scheduler and waits for a shutdown signal.
    It handles graceful shutdown when SIGTERM or SIGINT is received.
    """
    loop = asyncio.get_running_loop()

    # Register signal handlers for graceful shutdown using asyncio
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except (ValueError, OSError):
            # Signal handlers can only be registered in the main thread
            # On Windows, some signals may not be available
            logger.debug(f"Could not register signal handler for {sig}")

    try:
        start_scheduler()
        logger.info("Scheduler is running. Press Ctrl+C to stop.")

        # Wait for shutdown signal
        await _shutdown_event.wait()
    except asyncio.CancelledError:
        logger.info("Scheduler task was cancelled")
    finally:
        logger.info("Shutting down scheduler...")
        try:
            stop_scheduler()
        except Exception as e:
            logger.warning(f"Error during scheduler shutdown: {e}")
        finally:
            logger.info("Scheduler shutdown complete")


def run_scheduler() -> None:
    """Run the content sync scheduler as a standalone process.

    This is the main entry point for running the scheduler independently.
    It handles:
    - Signal handling for graceful shutdown (SIGTERM, SIGINT)
    - Proper async event loop management
    - Logging initialization

    Example:
        from src.english_tutor.scheduler import run_scheduler
        run_scheduler()
    """
    try:
        asyncio.run(_run_scheduler_async())
    except KeyboardInterrupt:
        logger.info("Shutdown complete")
        sys.exit(0)


__all__ = ["run_scheduler", "get_scheduler", "start_scheduler", "stop_scheduler"]
