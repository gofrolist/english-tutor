"""Structured logging infrastructure.

This module provides structured logging configuration for the application.
"""

import logging
import sys
from typing import Any


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name.

    Args:
        name: Logger name (typically __name__ of the calling module).

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)


def log_user_interaction(
    logger: logging.Logger,
    user_id: str,
    action: str,
    **kwargs: Any,
) -> None:
    """Log a user interaction with structured fields.

    Args:
        logger: Logger instance.
        user_id: User identifier.
        action: Action performed.
        **kwargs: Additional context fields to include in log.
    """
    logger.info(
        "User interaction",
        extra={
            "user_id": user_id,
            "action": action,
            **kwargs,
        },
    )


def log_content_delivery(
    logger: logging.Logger,
    user_id: str,
    content_id: str,
    content_type: str,
    **kwargs: Any,
) -> None:
    """Log content delivery event with structured fields.

    Args:
        logger: Logger instance.
        user_id: User identifier.
        content_id: Content identifier.
        content_type: Type of content delivered.
        **kwargs: Additional context fields to include in log.
    """
    logger.info(
        "Content delivery",
        extra={
            "user_id": user_id,
            "content_id": content_id,
            "content_type": content_type,
            **kwargs,
        },
    )


def log_quiz_submission(
    logger: logging.Logger,
    user_id: str,
    assessment_id: str,
    score: float,
    **kwargs: Any,
) -> None:
    """Log quiz submission event with structured fields.

    Args:
        logger: Logger instance.
        user_id: User identifier.
        assessment_id: Assessment identifier.
        score: Score achieved.
        **kwargs: Additional context fields to include in log.
    """
    logger.info(
        "Quiz submission",
        extra={
            "user_id": user_id,
            "assessment_id": assessment_id,
            "score": score,
            **kwargs,
        },
    )


def log_system_error(
    logger: logging.Logger,
    error: Exception,
    context: dict[str, Any] | None = None,
) -> None:
    """Log system error with structured fields.

    Args:
        logger: Logger instance.
        error: Exception that occurred.
        context: Additional context dictionary.
    """
    logger.error(
        "System error",
        extra={
            "error_type": type(error).__name__,
            "error_message": str(error),
            **(context or {}),
        },
        exc_info=True,
    )
