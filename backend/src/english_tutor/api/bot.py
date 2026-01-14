"""Telegram bot application structure.

This module initializes and configures the Telegram bot application.
"""

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from src.english_tutor.api.bot.handlers.assessment import (
    assess_command,
    handle_assessment_answer,
)
from src.english_tutor.api.bot.handlers.start import start_command
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


async def start_bot() -> None:
    """Start the Telegram bot."""
    app = get_bot_application()
    logger.info("Starting Telegram bot")
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

    Args:
        update: Telegram update object.
        context: Bot context.
    """
    log_system_error(
        logger,
        context.error,
        context={
            "update_id": update.update_id if update else None,
            "user_id": update.effective_user.id if update and update.effective_user else None,
        },
    )
