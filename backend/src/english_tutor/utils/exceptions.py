"""Error handling and exception classes.

This module provides custom exception classes for the application.
"""


class EnglishTutorError(Exception):
    """Base exception class for English Tutor application errors."""

    pass


class DatabaseError(EnglishTutorError):
    """Exception raised for database-related errors."""

    pass


class ConfigurationError(EnglishTutorError):
    """Exception raised for configuration-related errors."""

    pass


class ValidationError(EnglishTutorError):
    """Exception raised for validation errors."""

    pass


class AssessmentError(EnglishTutorError):
    """Exception raised for assessment-related errors."""

    pass


class TaskDeliveryError(EnglishTutorError):
    """Exception raised for task delivery errors."""

    pass


class ContentManagementError(EnglishTutorError):
    """Exception raised for content management errors."""

    pass


class TelegramBotError(EnglishTutorError):
    """Exception raised for Telegram bot API errors."""

    pass
