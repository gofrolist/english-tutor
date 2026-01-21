"""Telegram bot utility functions.

This module provides utility functions for working with Telegram bot API.
"""

from telegram import CallbackQuery
from telegram.error import BadRequest

from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)


async def safe_answer_callback_query(
    query: CallbackQuery | None,
    text: str | None = None,
    show_alert: bool = False,
) -> bool:
    """Safely answer a callback query, handling expired queries gracefully.

    Callback queries expire after approximately 1 minute. If the bot was down
    and messages were queued, attempting to answer expired queries will raise
    a BadRequest exception. This function catches that and logs it instead.

    Args:
        query: The callback query to answer, or None if not available.
        text: Optional text to show to the user.
        show_alert: If True, show the text as an alert instead of a notification.

    Returns:
        True if the query was answered successfully, False otherwise (including
        if the query was expired or None).
    """
    if query is None:
        return False

    try:
        await query.answer(text=text, show_alert=show_alert)
        return True
    except BadRequest as e:
        error_message = str(e).lower()
        # Check if the error is about expired/invalid query
        if "query is too old" in error_message or "query id is invalid" in error_message:
            logger.warning(
                "Attempted to answer expired callback query",
                extra={
                    "query_id": query.id if query else None,
                    "user_id": query.from_user.id if query and query.from_user else None,
                    "callback_data": query.data if query else None,
                    "error": str(e),
                },
            )
            return False
        # Re-raise other BadRequest errors (validation errors, etc.)
        raise


async def safe_edit_message_text(
    query: CallbackQuery | None,
    text: str,
    **kwargs,
) -> bool:
    """Safely edit a message from a callback query, handling expired queries gracefully.

    Args:
        query: The callback query containing the message to edit.
        text: The new text for the message.
        **kwargs: Additional arguments to pass to edit_message_text.

    Returns:
        True if the message was edited successfully, False otherwise.
    """
    if query is None or query.message is None:
        return False

    try:
        await query.edit_message_text(text, **kwargs)
        return True
    except BadRequest as e:
        error_message = str(e).lower()
        # Check if the error is about expired/invalid query or message not modified
        if (
            "query is too old" in error_message
            or "query id is invalid" in error_message
            or "message is not modified" in error_message
            or "message to edit not found" in error_message
        ):
            logger.warning(
                "Attempted to edit message from expired callback query or message not found",
                extra={
                    "query_id": query.id if query else None,
                    "user_id": query.from_user.id if query and query.from_user else None,
                    "callback_data": query.data if query else None,
                    "error": str(e),
                },
            )
            # Try to send a new message instead
            try:
                await query.message.reply_text(text, **kwargs)
                return True
            except Exception as reply_error:
                logger.error(
                    "Failed to send fallback message after edit failure",
                    extra={"error": str(reply_error)},
                )
                return False
        # Re-raise other BadRequest errors
        raise
