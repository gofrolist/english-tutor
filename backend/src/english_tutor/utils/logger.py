"""Structured logging infrastructure.

This module provides structured logging configuration for the application.
"""

import logging
import sys
from typing import Any

_logging_configured = False


def setup_logging(log_level: str = "INFO", force: bool = False) -> None:
    """Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        force: Force reconfiguration even if already configured.
    """
    global _logging_configured

    if _logging_configured and not force:
        return

    level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Create console handler with formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Custom formatter that includes extra fields
    class StructuredFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            # Base format
            base_msg = super().format(record)

            # Add extra fields if present
            if (
                hasattr(record, "user_id")
                or hasattr(record, "action")
                or hasattr(record, "error_type")
            ):
                extra_parts = []
                for key, value in record.__dict__.items():
                    if key not in [
                        "name",
                        "msg",
                        "args",
                        "created",
                        "filename",
                        "funcName",
                        "levelname",
                        "levelno",
                        "lineno",
                        "module",
                        "msecs",
                        "message",
                        "pathname",
                        "process",
                        "processName",
                        "relativeCreated",
                        "thread",
                        "threadName",
                        "exc_info",
                        "exc_text",
                        "stack_info",
                    ]:
                        extra_parts.append(f"{key}={value}")
                if extra_parts:
                    base_msg += f" | {' '.join(extra_parts)}"

            return base_msg

    formatter = StructuredFormatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)

    _logging_configured = True


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
