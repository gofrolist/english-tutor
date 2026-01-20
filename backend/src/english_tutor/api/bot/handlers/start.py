"""Telegram bot handler for /start command.

Handles the initial bot interaction when a user starts a conversation.
"""

from telegram import Update
from telegram.ext import ContextTypes

from src.english_tutor.api.bot.handlers.assessment import assess_command
from src.english_tutor.config import get_session_local
from src.english_tutor.models.user import User
from src.english_tutor.utils.logger import get_logger, log_user_interaction

logger = get_logger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command from user.

    Creates or retrieves user, and initiates assessment if user has no level.

    Args:
        update: Telegram update object.
        context: Bot context.
    """
    user_telegram_id = str(update.effective_user.id)
    username = update.effective_user.username

    log_user_interaction(
        logger,
        user_telegram_id,
        "start_command",
        username=username,
    )

    session_local = get_session_local()
    db = session_local()

    # Get or create user
    user = db.query(User).filter(User.telegram_user_id == user_telegram_id).first()

    try:
        if not user:
            user = User(
                telegram_user_id=user_telegram_id,
                username=username,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"New user created: {user_telegram_id}")

        welcome_message = (
            "Привет-привет!!\n\n"
            "🙋🏽‍♀️Я—твой карманный бот-репетитор английского\n\n"
            "Здесь строятся только здоровые отношения с языком👅🇺🇸\n\n"
            "Без:\n"
            "— стресса\n"
            "— самокритики\n"
            "— чувства, что ты «тупой» и «отстаёшь»\n\n"
            "Зато с:\n"
            "— заботливым подходом\n"
            "— маленькими шагами каждый день\n"
            "— ощущением «я реально понимаю»\n\n"
            "Моя цель сделать так, чтобы твой английский рос не «наугад»,\n"
            "а по понятному и комфортному плану!\n\n"
            "Поэтому давай начнём с короткого теста, чтобы понять твой уровень и подобрать задания именно под тебя!"
        )

        await update.message.reply_text(welcome_message)
    finally:
        db.close()

    # Automatically start assessment after welcome message
    # assess_command will create its own database session
    await assess_command(update, context)
