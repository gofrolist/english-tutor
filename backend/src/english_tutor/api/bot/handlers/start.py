"""Telegram bot handler for /start command.

Handles the initial bot interaction when a user starts a conversation.
"""

from telegram import Update
from telegram.ext import ContextTypes

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
            "Welcome to English Tutor Bot! 🇬🇧\n\n"
            "I'll help you improve your English through personalized learning tasks.\n\n"
        )

        if user.current_level is None:
            welcome_message += (
                "Let's start by assessing your English level. "
                "This will help me provide you with the right learning materials.\n\n"
                "Type /assess to begin the assessment quiz."
            )
        else:
            welcome_message += (
                f"Your current English level is: {user.current_level}\n\n"
                "You can:\n"
                "- Type /task to get a new learning task\n"
                "- Type /assess to retake the assessment"
            )

        await update.message.reply_text(welcome_message)
    finally:
        db.close()
