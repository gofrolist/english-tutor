"""Telegram bot application structure.

This module initializes and configures the Telegram bot application.
"""

from telegram import Update
from telegram.error import BadRequest, NetworkError, RetryAfter, TimedOut
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from src.english_tutor.api.bot.handlers.assessment import (
    assess_command,
    handle_assessment_answer,
    handle_assessment_ready,
)
from src.english_tutor.api.bot.handlers.progress import progress_command
from src.english_tutor.api.bot.handlers.start import handle_start_continue, start_command
from src.english_tutor.api.bot.handlers.tasks import (
    handle_task_answer,
    task_command,
)
from src.english_tutor.config import get_telegram_bot_token
from src.english_tutor.utils.logger import get_logger, log_system_error

logger = get_logger(__name__)

# Global bot application instance
bot_application: Application | None = None


def get_bot_application() -> Application:
    """Create and return Telegram bot application instance.

    Returns:
        Configured Telegram bot Application instance.
    """
    global bot_application
    if bot_application is None:
        token = get_telegram_bot_token()
        bot_application = Application.builder().token(token).build()

        # Register handlers
        bot_application.add_handler(CommandHandler("start", start_command))
        bot_application.add_handler(CommandHandler("assess", assess_command))
        bot_application.add_handler(CommandHandler("progress", progress_command))
        bot_application.add_handler(
            CallbackQueryHandler(handle_start_continue, pattern="^start_continue$")
        )
        bot_application.add_handler(
            CallbackQueryHandler(handle_assessment_ready, pattern="^start_assessment_ready\\|")
        )
        bot_application.add_handler(
            CallbackQueryHandler(handle_assessment_answer, pattern="^answer_")
        )
        bot_application.add_handler(CommandHandler("task", task_command))
        bot_application.add_handler(
            CallbackQueryHandler(handle_task_answer, pattern="^task_answer_")
        )

        # Register error handler
        bot_application.add_error_handler(handle_error)

        logger.info("Telegram bot application initialized with handlers")
    return bot_application


async def setup_webhook(webhook_url: str) -> None:
    """Set up Telegram webhook.

    Args:
        webhook_url: Full URL where Telegram should send updates (e.g., https://your-domain.com/webhook).
    """
    app = get_bot_application()
    logger.info(f"Setting up Telegram webhook at {webhook_url}")
    await app.initialize()
    await app.start()
    # Set webhook URL with Telegram
    await app.bot.set_webhook(url=webhook_url)
    logger.info("Telegram webhook set up successfully")


async def remove_webhook() -> None:
    """Remove Telegram webhook."""
    if bot_application is not None:
        logger.info("Removing Telegram webhook")
        try:
            await bot_application.bot.delete_webhook()
            logger.info("Telegram webhook removed successfully")
        except Exception as e:
            logger.warning(f"Error removing webhook: {e}")
        finally:
            await bot_application.stop()
            await bot_application.shutdown()
            logger.info("Telegram bot stopped")


async def start_bot() -> None:
    """Start the Telegram bot in polling mode (for local development)."""
    app = get_bot_application()
    logger.info("Starting Telegram bot in polling mode")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    logger.info("Telegram bot started and polling")


async def stop_bot() -> None:
    """Stop the Telegram bot."""
    if bot_application is not None:
        logger.info("Stopping Telegram bot")
        await bot_application.updater.stop()
        await bot_application.stop()
        await bot_application.shutdown()
        logger.info("Telegram bot stopped")


async def handle_error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in bot handlers.

    Gracefully handles expired callback queries and other common Telegram API errors
    that don't require user notification or error-level logging.

    Args:
        update: Telegram update object.
        context: Bot context.
    """
    error = context.error
    error_message = str(error).lower() if error else ""

    # Handle expired callback queries gracefully (common when bot restarts)
    if isinstance(error, BadRequest) and (
        "query is too old" in error_message or "query id is invalid" in error_message
    ):
        logger.debug(
            "Expired callback query handled gracefully",
            extra={
                "update_id": update.update_id if update else None,
                "user_id": update.effective_user.id if update and update.effective_user else None,
                "callback_query_id": (
                    update.callback_query.id if update and update.callback_query else None
                ),
            },
        )
        return

    # Handle message not modified errors (common when editing messages)
    if isinstance(error, BadRequest) and "message is not modified" in error_message:
        logger.debug(
            "Message not modified (no changes detected)",
            extra={
                "update_id": update.update_id if update else None,
                "user_id": update.effective_user.id if update and update.effective_user else None,
            },
        )
        return

    # Handle network errors and timeouts (these are transient)
    # Note: BadRequest is a subclass of NetworkError, so we check it separately above
    if isinstance(error, NetworkError) and not isinstance(error, BadRequest):
        logger.warning(
            "Network error occurred",
            extra={
                "update_id": update.update_id if update else None,
                "user_id": update.effective_user.id if update and update.effective_user else None,
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
        )
        return

    if isinstance(error, TimedOut):
        logger.warning(
            "Network error occurred",
            extra={
                "update_id": update.update_id if update else None,
                "user_id": update.effective_user.id if update and update.effective_user else None,
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
        )
        return

    # Handle rate limiting (Telegram will retry automatically)
    if isinstance(error, RetryAfter):
        logger.warning(
            "Rate limited by Telegram API",
            extra={
                "update_id": update.update_id if update else None,
                "user_id": update.effective_user.id if update and update.effective_user else None,
                "retry_after": error.retry_after,
            },
        )
        return

    # Log all other errors as system errors
    log_system_error(
        logger,
        error,
        context={
            "update_id": update.update_id if update else None,
            "user_id": update.effective_user.id if update and update.effective_user else None,
        },
    )
