"""Shared utilities for content synchronization.

This module provides common utilities and types used across content sync services.
"""

import sys
from typing import TypedDict

from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)


class SyncStats(TypedDict, total=False):
    """Statistics returned from sync operations.

    Attributes:
        tasks_created: Number of tasks created during sync.
        tasks_updated: Number of tasks updated during sync.
        tasks_deleted: Number of tasks deleted during sync.
        tasks_skipped: Number of tasks skipped (no changes).
        questions_created: Number of questions created during sync.
        questions_updated: Number of questions updated during sync.
        questions_deleted: Number of questions deleted during sync.
        questions_skipped: Number of questions skipped (no changes).
        assessment_questions_created: Number of assessment questions created.
        assessment_questions_updated: Number of assessment questions updated.
        assessment_questions_skipped: Number of assessment questions skipped.
        errors: Number of errors encountered during sync.
    """

    tasks_created: int
    tasks_updated: int
    tasks_deleted: int
    tasks_skipped: int
    questions_created: int
    questions_updated: int
    questions_deleted: int
    questions_skipped: int
    assessment_questions_created: int
    assessment_questions_updated: int
    assessment_questions_skipped: int
    errors: int


def log_sync(message: str, level: str = "info") -> None:
    """Log sync message and print to stderr for immediate visibility.

    This helper provides dual logging during sync operations:
    - Logs to the structured logger for persistence
    - Prints to stderr for immediate visibility during long-running syncs

    Args:
        message: The message to log.
        level: Log level (info, warning, error, debug). Defaults to "info".

    Example:
        >>> log_sync("Starting content sync...")
        >>> log_sync("Failed to sync task", level="error")
    """
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(message)
    print(f"[SYNC {level.upper()}] {message}", file=sys.stderr)
    sys.stderr.flush()
