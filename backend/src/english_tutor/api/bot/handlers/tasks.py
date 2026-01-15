"""Telegram bot handlers for task delivery and completion flow.

Handles task requests, content delivery (text/audio/video), question delivery,
answer collection, and feedback delivery.
"""

from typing import Any
from uuid import UUID

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.english_tutor.config import get_session_local
from src.english_tutor.models.question import Question
from src.english_tutor.models.task import Task, TaskType
from src.english_tutor.models.user import User
from src.english_tutor.services.task_completion import TaskCompletionService
from src.english_tutor.services.task_delivery import TaskDeliveryService
from src.english_tutor.utils.exceptions import TaskDeliveryError
from src.english_tutor.utils.logger import get_logger, log_user_interaction

logger = get_logger(__name__)
task_delivery_service = TaskDeliveryService()
task_completion_service = TaskCompletionService()


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
        await update.message.reply_audio(
            audio=task.content_audio_url,
            caption=task.title,
        )
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
        await update.message.reply_video(
            video=task.content_video_url,
            caption=task.title,
        )
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
    await query.answer()

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
            await query.edit_message_text("Пользователь не найден. Пожалуйста, начните с /start.")
            return

        user_data = _get_user_data(context)
        task_id_str = user_data.get("current_task_id")
        if not task_id_str:
            await query.edit_message_text(
                "Активное задание не найдено. Введите /task, чтобы получить новое задание."
            )
            return

        task_id = UUID(task_id_str)
        task = db.query(Task).filter(Task.id == task_id).first()

        if not task:
            await query.edit_message_text("Задание не найдено.")
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
            await query.edit_message_text(
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
        await query.edit_message_text(
            f"Произошла ошибка: {str(e)}\n\nПожалуйста, попробуйте снова."
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

        await update.callback_query.edit_message_text(
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
        await update.callback_query.edit_message_text(
            "Произошла ошибка при завершении задания. Пожалуйста, попробуйте снова."
        )
