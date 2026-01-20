"""Telegram bot handlers for assessment flow.

Handles assessment initiation, question delivery, answer collection, and result delivery.
"""

from typing import Any
from uuid import UUID

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.english_tutor.config import get_session_local
from src.english_tutor.models.assessment import Assessment, AssessmentStatus
from src.english_tutor.models.assessment_question import AssessmentQuestion
from src.english_tutor.models.user import User
from src.english_tutor.services.assessment import AssessmentService
from src.english_tutor.utils.logger import get_logger, log_quiz_submission, log_user_interaction

logger = get_logger(__name__)
assessment_service = AssessmentService()


def _get_user_data(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    """Return user_data dict, initializing if missing."""
    if context.user_data is None:
        context.user_data = {}
    return context.user_data


async def assess_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /assess command to initiate assessment.

    Args:
        update: Telegram update object.
        context: Bot context.
    """
    user_telegram_id = str(update.effective_user.id)

    log_user_interaction(
        logger,
        user_telegram_id,
        "assess_command",
    )

    session_local = get_session_local()
    db = session_local()

    try:
        # Get or create user
        user = db.query(User).filter(User.telegram_user_id == user_telegram_id).first()
        if not user:
            await update.message.reply_text("Пожалуйста, сначала запустите бота командой /start.")
            return

        # Check for existing in-progress assessment and abandon it
        existing_assessment = (
            db.query(Assessment)
            .filter(
                Assessment.user_id == user.id,
                Assessment.status == AssessmentStatus.IN_PROGRESS,
            )
            .first()
        )

        if existing_assessment:
            # Abandon the existing assessment to start a new one
            await assessment_service.abandon_assessment(existing_assessment.id, db)
            # Clear context data from the abandoned assessment
            user_data = _get_user_data(context)
            user_data.pop("current_assessment_id", None)
            user_data.pop("current_question_index", None)
            logger.info(
                f"Abandoned existing assessment {existing_assessment.id} to start new one",
                extra={"user_id": str(user.id), "assessment_id": str(existing_assessment.id)},
            )

        # Start new assessment (questions will be selected automatically)
        assessment = await assessment_service.start_assessment(
            user.id,
            db,
            question_ids=None,  # None triggers automatic selection
        )

        # Store assessment ID in context for answer collection
        user_data = _get_user_data(context)
        user_data["current_assessment_id"] = str(assessment.id)

        await update.message.reply_text(
            "Отлично! Давайте оценим ваш уровень английского.\n\n"
            "Я задам вам несколько вопросов. "
            "Пожалуйста, отвечайте на каждый вопрос, выбирая один из вариантов.\n\n"
            "Готовы? Начинаем!"
        )

        # Send first question
        await send_assessment_question(update, context, assessment.id, db)
    finally:
        db.close()


async def send_assessment_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    assessment_id: UUID,
    db,
) -> None:
    """Send an assessment question to the user.

    Args:
        update: Telegram update object.
        context: Bot context.
        assessment_id: Assessment UUID.
        db: Database session.
    """
    try:
        assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
        if not assessment:
            # Handle both message and callback query cases
            if update.message:
                await update.message.reply_text("Оценка не найдена.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("Оценка не найдена.")
            return

        # Get current question index from context
        user_data = _get_user_data(context)
        current_question_index = user_data.get("current_question_index", 0)
        question_ids = list(assessment.questions) if assessment.questions else []

        if current_question_index >= len(question_ids):
            # All questions answered, complete assessment
            await complete_and_deliver_result(update, context, assessment_id, db)
            return

        # Get current question
        question_id_str = question_ids[current_question_index]
        question_uuid = (
            UUID(question_id_str) if isinstance(question_id_str, str) else question_id_str
        )
        question = (
            db.query(AssessmentQuestion).filter(AssessmentQuestion.id == question_uuid).first()
        )

        if not question:
            # Handle both message and callback query cases
            if update.message:
                await update.message.reply_text("Вопрос не найден.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("Вопрос не найден.")
            return

        # Build keyboard with answer options
        keyboard = [
            [InlineKeyboardButton(option, callback_data=f"answer_{current_question_index}_{i}")]
            for i, option in enumerate(question.answer_options)
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send question
        question_number = current_question_index + 1
        total_questions = len(question_ids)
        message_text = f"Вопрос {question_number}/{total_questions}\n\n{question.question_text}"

        # Handle both message and callback query cases
        if update.message:
            await update.message.reply_text(
                message_text,
                reply_markup=reply_markup,
            )
        elif update.callback_query:
            # Send new message after callback query
            await update.callback_query.message.reply_text(
                message_text,
                reply_markup=reply_markup,
            )
    finally:
        db.close()


async def handle_assessment_answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle assessment answer from inline keyboard callback.

    Args:
        update: Telegram update object.
        context: Bot context.
    """
    query = update.callback_query
    await query.answer()

    user_telegram_id = str(update.effective_user.id)
    answer_data = query.data  # Format: "answer_0", "answer_1", etc.

    log_user_interaction(
        logger,
        user_telegram_id,
        "assessment_answer",
        answer=answer_data,
    )

    session_local = get_session_local()
    db = session_local()

    try:
        user = db.query(User).filter(User.telegram_user_id == user_telegram_id).first()
        if not user:
            await query.edit_message_text("Пользователь не найден. Пожалуйста, начните с /start.")
            return

        assessment_id_str = context.user_data.get("current_assessment_id")
        if not assessment_id_str:
            await query.edit_message_text("Активная оценка не найдена. Введите /assess для начала.")
            return

        assessment_id = UUID(assessment_id_str)
        assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()

        if not assessment or assessment.status != AssessmentStatus.IN_PROGRESS:
            await query.edit_message_text("Оценка не найдена или уже завершена.")
            return

        # Extract question index and answer index from callback data
        # Format: "answer_{question_index}_{answer_index}"
        parts = answer_data.split("_")
        if len(parts) != 3:
            await query.edit_message_text("Неверный формат ответа.")
            return

        question_index = int(parts[1])
        answer_index = int(parts[2])

        # Get question ID from assessment
        question_ids = assessment.questions
        if question_index >= len(question_ids):
            await query.edit_message_text("Неверный индекс вопроса.")
            return

        question_id_str = question_ids[question_index]

        # Store answer in assessment.answers
        # assessment.answers is JSONB, convert to dict, update, and assign back
        current_answers = assessment.answers if assessment.answers else {}
        if not isinstance(current_answers, dict):
            current_answers = {}
        updated_answers = dict(current_answers)
        updated_answers[question_id_str] = answer_index
        assessment.answers = updated_answers
        db.commit()

        # Update context
        user_data = _get_user_data(context)
        user_data["current_question_index"] = question_index + 1

        # Check if more questions remain
        if question_index + 1 < len(question_ids):
            # Send next question
            await query.answer("Ответ записан!")
            await send_assessment_question(update, context, assessment_id, db)
        else:
            # All questions answered, complete assessment
            await query.answer("Последний ответ записан!")
            await complete_and_deliver_result(update, context, assessment_id, db)
    finally:
        db.close()


async def complete_and_deliver_result(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    assessment_id: UUID,
    db,
) -> None:
    """Complete assessment and deliver result to user.

    Args:
        update: Telegram update object.
        context: Bot context.
        assessment_id: Assessment UUID.
        db: Database session.
    """
    try:
        assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
        if not assessment:
            if update.callback_query:
                await update.callback_query.edit_message_text("Оценка не найдена.")
            else:
                await update.message.reply_text("Оценка не найдена.")
            return

        user = db.query(User).filter(User.id == assessment.user_id).first()

        # Get actual questions from database
        question_ids_list = list(assessment.questions) if assessment.questions else []
        questions = assessment_service.get_assessment_questions(db, question_ids_list)
        answers = dict(assessment.answers) if assessment.answers else {}

        # Calculate score and determine level
        score = assessment_service.calculate_score(questions, answers)
        level = assessment_service.determine_level(score)

        # Complete assessment
        await assessment_service.complete_assessment(
            assessment_id,
            answers,
            score,
            level,
            db,
        )

        # Update user level
        if user is not None:
            user.current_level = level
            db.commit()

        # Deliver result
        result_message = (
            "Оценка завершена!\n\n"
            f"Ваш уровень английского: {level}\n\n"
            f"Результат: {score * 100:.1f}%\n\n"
            "Согласно Общеевропейским компетенциям владения иностранным языком (CEFR):\n"
            "- A1-A2: Начальный уровень\n"
            "- B1-B2: Средний уровень\n"
            "- C1-C2: Продвинутый уровень\n\n"
            "Теперь вы можете начать обучение с заданиями, подходящими вашему уровню!\n"
            "Введите /task, чтобы получить первое задание."
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(result_message)
        else:
            await update.message.reply_text(result_message)

        # Clear assessment from context
        context.user_data.pop("current_assessment_id", None)
        context.user_data.pop("current_question_index", None)

        if user is not None:
            log_quiz_submission(
                logger,
                str(user.telegram_user_id),
                str(assessment_id),
                score,
                level=level,
            )
    finally:
        db.close()
