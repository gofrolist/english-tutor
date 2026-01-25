"""Telegram bot handler for /progress command.

Displays user learning progress including activity, quality, and level mastery metrics.
"""

from telegram import Update
from telegram.ext import ContextTypes

from src.english_tutor.config import get_session_local
from src.english_tutor.models.user import User
from src.english_tutor.services.progress import ProgressService
from src.english_tutor.utils.logger import get_logger, log_user_interaction

logger = get_logger(__name__)

# Skill names in Russian
SKILL_NAMES = {
    "listening": "Аудирование",
    "reading": "Чтение",
    "writing": "Письмо",
    "speaking": "Говорение",
    "grammar": "Грамматика",
    "vocabulary": "Лексика",
    "pronunciation": "Произношение",
}

# Level names in Russian
LEVEL_NAMES = {
    "A1": "A1",
    "A2": "A2",
    "B1": "B1",
    "B2": "B2",
    "C1": "C1",
    "C2": "C2",
}


def _format_skill_name(domain: str) -> str:
    """Format skill domain name in Russian.

    Args:
        domain: Language domain (e.g., "grammar", "listening")

    Returns:
        Russian name for the skill
    """
    return SKILL_NAMES.get(domain, domain.capitalize())


def _pluralize_days(count: int) -> str:
    """Get correct plural form of 'день' based on count.

    Rules for Russian pluralization:
    - 1, 21, 31, 41, 51, 61, 71, 81, 91, 101... → "день"
    - 2, 3, 4, 22, 23, 24, 32, 33, 34... → "дня"
    - 5-20, 25-30, 35-40... → "дней"

    Args:
        count: Number of days.

    Returns:
        Correct plural form: "день", "дня", or "дней".
    """
    remainder_10 = count % 10
    remainder_100 = count % 100

    # Special cases for 11-14 (always "дней")
    if 11 <= remainder_100 <= 14:
        return "дней"

    # Cases based on last digit
    if remainder_10 == 1:
        return "день"
    elif 2 <= remainder_10 <= 4:
        return "дня"
    else:
        return "дней"


async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /progress command to display user progress.

    Args:
        update: Telegram update object.
        context: Bot context.
    """
    user_telegram_id = str(update.effective_user.id)

    log_user_interaction(
        logger,
        user_telegram_id,
        "progress_command",
    )

    session_local = get_session_local()
    db = session_local()

    try:
        # Get user
        user = db.query(User).filter(User.telegram_user_id == user_telegram_id).first()
        if not user:
            message = update.effective_message
            if message:
                await message.reply_text(
                    "Вы не зарегистрированы. Используйте /start для начала работы."
                )
            return

        # Calculate progress metrics
        progress_service = ProgressService()
        metrics = progress_service.calculate_progress(user_telegram_id, db)

        # Format progress message
        message_parts = ["📊 *Ваш прогресс*\n"]

        # Activity section
        message_parts.append("📈 *Активность*\n")
        message_parts.append(f"Выполнено заданий: *{metrics.completed_tasks_count}*")
        message_parts.append(f"Активных дней в этом месяце: *{metrics.active_days_this_month}*")
        message_parts.append(
            f"Текущая серия: *{metrics.current_streak_days} {_pluralize_days(metrics.current_streak_days)}*\n"
        )

        # Quality section
        message_parts.append("🎯 *Качество выполнения*\n")

        if metrics.overall_accuracy is not None:
            message_parts.append(f"Общая точность: *{metrics.overall_accuracy:.1f}%*\n")
        else:
            message_parts.append("Общая точность: *Нет данных*\n")

        # Skill-specific accuracy
        skill_lines = []
        for domain in [
            "grammar",
            "vocabulary",
            "listening",
            "reading",
            "writing",
            "speaking",
            "pronunciation",
        ]:
            accuracy = metrics.skill_accuracy.get(domain)
            if accuracy is not None:
                skill_name = _format_skill_name(domain)
                skill_lines.append(f"{skill_name}: *{accuracy:.1f}%*")
            else:
                skill_name = _format_skill_name(domain)
                skill_lines.append(f"{skill_name}: *Недостаточно данных*")

        if skill_lines:
            message_parts.append("\n".join(skill_lines))
            message_parts.append("")

        # Level mastery section
        message_parts.append("🏆 *Освоение уровней*\n")

        level_lines = []
        for level in ["A1", "A2", "B1", "B2", "C1", "C2"]:
            mastery = metrics.level_mastery.get(level)
            if mastery is not None:
                level_lines.append(f"{level}: *{mastery:.1f}%*")
            else:
                level_lines.append(f"{level}: *Нет данных*")

        if level_lines:
            message_parts.append("\n".join(level_lines))

        # Send message
        message_text = "\n".join(message_parts)
        message = update.effective_message
        if message:
            await message.reply_text(message_text, parse_mode="Markdown")

    except Exception as e:
        logger.error("Error displaying progress", extra={"error": str(e)}, exc_info=True)
        message = update.effective_message
        if message:
            await message.reply_text(
                "Произошла ошибка при получении данных о прогрессе. Пожалуйста, попробуйте позже."
            )
    finally:
        db.close()
