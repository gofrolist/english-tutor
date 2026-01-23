"""Telegram bot handlers for task delivery and completion flow.

Handles task requests, content delivery (text/audio/video), question delivery,
answer collection, and feedback delivery.
"""

import re
from typing import Any, Optional
from uuid import UUID

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.english_tutor.api.bot.utils import safe_answer_callback_query, safe_edit_message_text
from src.english_tutor.config import get_session_local
from src.english_tutor.models.question import Question
from src.english_tutor.models.task import Task, TaskType
from src.english_tutor.models.user import User
from src.english_tutor.services.google_drive import GoogleDriveService
from src.english_tutor.services.media_cache import MediaCacheService
from src.english_tutor.services.task_completion import TaskCompletionService
from src.english_tutor.services.task_delivery import TaskDeliveryService
from src.english_tutor.utils.exceptions import ContentManagementError, TaskDeliveryError
from src.english_tutor.utils.logger import get_logger, log_user_interaction

logger = get_logger(__name__)
task_delivery_service = TaskDeliveryService()
task_completion_service = TaskCompletionService()
media_cache_service = MediaCacheService()


def _extract_google_drive_file_id(url: str) -> str | None:
    """Extract Google Drive file ID from URL.

    Args:
        url: Google Drive URL

    Returns:
        File ID if URL is a Google Drive URL, None otherwise
    """
    # Pattern for URLs like: https://drive.google.com/uc?export=download&id=FILE_ID
    match = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)

    # Pattern for URLs like: https://drive.google.com/file/d/FILE_ID/view
    match = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)

    return None


def _download_file_content(url: str, file_id: Optional[str] = None) -> bytes:
    """Download file content from URL with caching support.

    Tries to use cache first, then downloads from Google Drive API if URL is a Google Drive URL,
    otherwise uses requests to download directly. Caches the result for future use.

    Args:
        url: File URL
        file_id: Optional file identifier for caching (if None, uses URL as identifier)

    Returns:
        File content as bytes

    Raises:
        TaskDeliveryError: If download fails
    """
    # Use URL as cache key if file_id not provided
    cache_key = file_id or url

    # Check cache first
    cached_content = media_cache_service.get(cache_key)
    if cached_content is not None:
        logger.info(f"Using cached file for: {cache_key[:20]}...")
        return cached_content

    # Try to extract Google Drive file ID
    drive_file_id = _extract_google_drive_file_id(url)
    if drive_file_id:
        try:
            drive_service = GoogleDriveService()
            content = drive_service.download_file_content(drive_file_id)
            # Cache the downloaded content
            try:
                media_cache_service.put(cache_key, content)
            except ContentManagementError as cache_error:
                logger.warning(f"Failed to cache file (continuing anyway): {cache_error}")
            return content
        except ContentManagementError as e:
            logger.warning(f"Failed to download from Google Drive API, trying direct download: {e}")

    # Fallback to direct download
    try:
        response = requests.get(url, timeout=30, allow_redirects=True)
        response.raise_for_status()
        content = response.content
        # Cache the downloaded content
        try:
            media_cache_service.put(cache_key, content)
        except ContentManagementError as cache_error:
            logger.warning(f"Failed to cache file (continuing anyway): {cache_error}")
        return content
    except requests.RequestException as e:
        logger.error(f"Failed to download file from URL: {e}")
        raise TaskDeliveryError(f"Failed to download file: {e}") from e


def _get_user_data(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    """Return user_data dict, initializing if missing."""
    if context.user_data is None:
        context.user_data = {}
    return context.user_data


async def task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /task command to request a new learning task.

    Args:
        update: Telegram update object.
        context: Bot context.
    """
    user_telegram_id = str(update.effective_user.id)

    log_user_interaction(
        logger,
        user_telegram_id,
        "task_command",
    )

    session_local = get_session_local()
    db = session_local()

    try:
        # Get user
        user = db.query(User).filter(User.telegram_user_id == user_telegram_id).first()
        if not user:
            await update.message.reply_text("Пожалуйста, сначала запустите бота командой /start.")
            return

        # Check if user has a level
        if not user.current_level:
            await update.message.reply_text(
                "Пожалуйста, сначала пройдите оценку, чтобы определить ваш уровень английского.\n\n"
                "Введите /assess, чтобы начать оценку."
            )
            return

        # Select task for user
        task = task_delivery_service.select_task_for_user(user.id, db)

        if not task:
            await update.message.reply_text(
                "Извините, сейчас нет заданий для вашего уровня.\n\n"
                "Попробуйте позже или введите /assess, чтобы пройти оценку заново."
            )
            return

        # Store task ID in context for answer collection
        user_data = _get_user_data(context)
        user_data["current_task_id"] = str(task.id)
        user_data["task_answers"] = {}

        # Deliver task content based on type
        if task.type == TaskType.TEXT.value:
            await deliver_text_task(update, task, db)
        elif task.type == TaskType.AUDIO.value:
            await deliver_audio_task(update, task, db)
        elif task.type == TaskType.VIDEO.value:
            await deliver_video_task(update, task, db)

        # Send questions if task has questions
        questions = (
            db.query(Question).filter(Question.task_id == task.id).order_by(Question.order).all()
        )
        if questions:
            await send_first_question(update, context, questions[0], db)

    except TaskDeliveryError as e:
        logger.error("Task delivery error", extra={"error": str(e)})
        await update.message.reply_text(
            f"Произошла ошибка при выдаче задания: {str(e)}\n\nПожалуйста, попробуйте позже."
        )
    finally:
        db.close()


async def deliver_text_task(update: Update, task: Task, db) -> None:
    """Deliver text task content.

    Args:
        update: Telegram update object.
        task: Task object.
        db: Database session.
    """
    message = f"📝 **{task.title}**\n\n{task.content_text}"

    if task.explanation:
        message += f"\n\n💡 **Объяснение:**\n{task.explanation}"

    await update.message.reply_text(
        message,
        parse_mode="Markdown",
    )

    logger.info(
        "Text task delivered",
        extra={"task_id": str(task.id), "task_type": task.type},
    )


async def deliver_audio_task(update: Update, task: Task, db) -> None:
    """Deliver audio task content.

    Args:
        update: Telegram update object.
        task: Task object.
        db: Database session.
    """
    await update.message.reply_text(
        f"🎧 **{task.title}**\n\nПожалуйста, прослушайте аудиофайл ниже."
    )

    # Send audio file
    if task.content_audio_url:
        try:
            # Extract file ID for better caching
            drive_file_id = _extract_google_drive_file_id(task.content_audio_url)
            # Download file content (with caching)
            audio_bytes = _download_file_content(task.content_audio_url, file_id=drive_file_id)

            # Send audio as bytes
            await update.message.reply_audio(
                audio=audio_bytes,
                caption=task.title,
            )
        except TaskDeliveryError as e:
            logger.error(f"Failed to deliver audio task: {e}")
            await update.message.reply_text(
                f"Ошибка при загрузке аудиофайла: {str(e)}\n\nПожалуйста, попробуйте позже."
            )
            return
    else:
        await update.message.reply_text("Ошибка: отсутствует URL аудио контента.")

    logger.info(
        "Audio task delivered",
        extra={"task_id": str(task.id), "task_type": task.type},
    )


async def deliver_video_task(update: Update, task: Task, db) -> None:
    """Deliver video task content.

    Args:
        update: Telegram update object.
        task: Task object.
        db: Database session.
    """
    await update.message.reply_text(f"🎥 **{task.title}**\n\nПожалуйста, посмотрите видео ниже.")

    # Send video file
    if task.content_video_url:
        try:
            # Extract file ID for better caching
            drive_file_id = _extract_google_drive_file_id(task.content_video_url)
            # Download file content (with caching)
            video_bytes = _download_file_content(task.content_video_url, file_id=drive_file_id)

            # Send video as bytes
            await update.message.reply_video(
                video=video_bytes,
                caption=task.title,
            )
        except TaskDeliveryError as e:
            logger.error(f"Failed to deliver video task: {e}")
            await update.message.reply_text(
                f"Ошибка при загрузке видеофайла: {str(e)}\n\nПожалуйста, попробуйте позже."
            )
            return
    else:
        await update.message.reply_text("Ошибка: отсутствует URL видео контента.")

    logger.info(
        "Video task delivered",
        extra={"task_id": str(task.id), "task_type": task.type},
    )


async def send_first_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    question: Question,
    db,
) -> None:
    """Send the first question after task content.

    Args:
        update: Telegram update object.
        context: Bot context.
        question: First Question object.
        db: Database session.
    """
    await send_question(update, context, question, db)


async def send_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    question: Question,
    db,
) -> None:
    """Send a question with inline keyboard options.

    Args:
        update: Telegram update object.
        context: Bot context.
        question: Question object.
        db: Database session.
    """
    keyboard = [
        [InlineKeyboardButton(option, callback_data=f"task_answer_{question.id}_{i}")]
        for i, option in enumerate(question.answer_options)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        question.question_text,
        reply_markup=reply_markup,
    )

    logger.info(
        "Question delivered",
        extra={
            "question_id": str(question.id),
            "task_id": str(context.user_data.get("current_task_id")),
        },
    )


async def handle_task_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle task answer callback query.

    Args:
        update: Telegram update object.
        context: Bot context.
    """
    query = update.callback_query
    # Answer query safely (may fail silently if expired)
    await safe_answer_callback_query(query)

    user_telegram_id = str(update.effective_user.id)
    # Callback data format: "task_answer_{question_id}_{answer_index}"
    callback_data = query.data
    parts = callback_data.split("_")
    question_id_str = parts[2]  # question_id
    answer_index = int(parts[3])  # answer_index

    log_user_interaction(
        logger,
        user_telegram_id,
        "task_answer",
        question_id=question_id_str,
        answer_index=answer_index,
    )

    session_local = get_session_local()
    db = session_local()

    try:
        user = db.query(User).filter(User.telegram_user_id == user_telegram_id).first()
        if not user:
            await safe_edit_message_text(
                query, "Пользователь не найден. Пожалуйста, начните с /start."
            )
            return

        user_data = _get_user_data(context)
        task_id_str = user_data.get("current_task_id")
        if not task_id_str:
            await safe_edit_message_text(
                query, "Активное задание не найдено. Введите /task, чтобы получить новое задание."
            )
            return

        task_id = UUID(task_id_str)
        task = db.query(Task).filter(Task.id == task_id).first()

        if not task:
            await safe_edit_message_text(query, "Задание не найдено.")
            return

        # Store answer
        if "task_answers" not in user_data:
            user_data["task_answers"] = {}

        user_data["task_answers"][question_id_str] = answer_index

        # Get all questions for this task
        questions = (
            db.query(Question).filter(Question.task_id == task_id).order_by(Question.order).all()
        )

        # Find current question index
        current_question_idx = None
        for idx, q in enumerate(questions):
            if str(q.id) == question_id_str:
                current_question_idx = idx
                break

        if current_question_idx is None:
            await query.edit_message_text("Вопрос не найден.")
            return

        # Check if there are more questions
        if current_question_idx < len(questions) - 1:
            # Send next question
            next_question = questions[current_question_idx + 1]
            await safe_edit_message_text(
                query,
                f"✓ Ответ записан!\n\n{next_question.question_text}",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                option, callback_data=f"task_answer_{next_question.id}_{i}"
                            )
                        ]
                        for i, option in enumerate(next_question.answer_options)
                    ]
                ),
            )
        else:
            # All questions answered, complete task
            await complete_task_and_send_feedback(update, context, user.id, task_id, db)

    except (TaskDeliveryError, ValueError, Exception) as e:
        logger.error("Task answer handling error", extra={"error": str(e)})
        await safe_edit_message_text(
            query, f"Произошла ошибка: {str(e)}\n\nПожалуйста, попробуйте снова."
        )
    finally:
        db.close()


async def complete_task_and_send_feedback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: UUID,
    task_id: UUID,
    db,
) -> None:
    """Complete task and send feedback to user.

    Args:
        update: Telegram update object.
        context: Bot context.
        user_id: User UUID.
        task_id: Task UUID.
        db: Database session.
    """
    try:
        answers = context.user_data.get("task_answers", {})

        # Complete task
        progress = task_completion_service.complete_task(
            user_id,
            task_id,
            answers,
            db,
        )

        # Prepare feedback message
        percentage = progress.percentage_correct
        score_emoji = "🎉" if percentage >= 80 else "👍" if percentage >= 60 else "📚"

        feedback_message = (
            f"{score_emoji} **Задание выполнено!**\n\n"
            f"Ваш результат: **{percentage:.1f}%**\n"
            f"Заработано баллов: **{progress.score:.1f}**\n\n"
        )

        if percentage >= 80:
            feedback_message += "Отличная работа! Продолжайте в том же духе! 🌟"
        elif percentage >= 60:
            feedback_message += "Хорошая работа! Вы делаете успехи. 💪"
        else:
            feedback_message += "Продолжайте практиковаться! Вы учитесь. 📖"

        # Get task for explanation
        task = db.query(Task).filter(Task.id == task_id).first()
        if task and task.explanation:
            feedback_message += f"\n\n💡 **Объяснение:**\n{task.explanation}"

        await safe_edit_message_text(
            update.callback_query,
            feedback_message,
            parse_mode="Markdown",
        )

        # Clear task context
        context.user_data.pop("current_task_id", None)
        context.user_data.pop("task_answers", None)

        logger.info(
            "Task completed and feedback sent",
            extra={
                "user_id": str(user_id),
                "task_id": str(task_id),
                "score": progress.score,
                "percentage": percentage,
            },
        )

    except Exception as e:
        logger.error("Error completing task", extra={"error": str(e)})
        await safe_edit_message_text(
            update.callback_query,
            "Произошла ошибка при завершении задания. Пожалуйста, попробуйте снова.",
        )
