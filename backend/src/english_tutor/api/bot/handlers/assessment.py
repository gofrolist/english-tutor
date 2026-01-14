"""Telegram bot handlers for assessment flow.

Handles assessment initiation, question delivery, answer collection, and result delivery.
"""

from typing import Any
from uuid import UUID

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.english_tutor.config import get_session_local
from src.english_tutor.models.assessment import Assessment, AssessmentStatus
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
            await update.message.reply_text("Please start the bot first with /start command.")
            return

        # Check for existing in-progress assessment
        existing_assessment = (
            db.query(Assessment)
            .filter(
                Assessment.user_id == user.id,
                Assessment.status == AssessmentStatus.IN_PROGRESS,
            )
            .first()
        )

        if existing_assessment:
            await update.message.reply_text(
                "You already have an assessment in progress. "
                "Please complete it first or type /cancel to abandon it."
            )
            return

        # TODO: Select assessment questions (for now, use empty list)
        question_ids = []

        # Start new assessment
        assessment = await assessment_service.start_assessment(
            user.id,
            db,
            question_ids=question_ids,
        )

        # Store assessment ID in context for answer collection
        user_data = _get_user_data(context)
        user_data["current_assessment_id"] = str(assessment.id)

        await update.message.reply_text(
            "Great! Let's assess your English level.\n\n"
            "I'll ask you a series of questions. "
            "Please answer each question by selecting one of the options.\n\n"
            "Ready? Let's begin!"
        )

        # TODO: Send first question
        # For now, send a placeholder message
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
            await update.message.reply_text("Assessment not found.")
            return

        # TODO: Get next question from assessment.questions
        # For now, send a placeholder
        question_text = "Sample question: What is the past tense of 'go'?"
        answer_options = ["goed", "went", "gone", "going"]
        _correct_answer = 1

        keyboard = [
            [InlineKeyboardButton(option, callback_data=f"answer_{i}")]
            for i, option in enumerate(answer_options)
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            question_text,
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
            await query.edit_message_text("User not found. Please start with /start.")
            return

        assessment_id_str = context.user_data.get("current_assessment_id")
        if not assessment_id_str:
            await query.edit_message_text("No active assessment found. Type /assess to start.")
            return

        assessment_id = UUID(assessment_id_str)
        assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()

        if not assessment or assessment.status != AssessmentStatus.IN_PROGRESS:
            await query.edit_message_text("Assessment not found or already completed.")
            return

        # Extract answer index from callback data
        answer_index = int(answer_data.split("_")[1])

        # TODO: Store answer in assessment.answers
        # For now, collect answers in context
        user_data = _get_user_data(context)
        if "assessment_answers" not in user_data:
            user_data["assessment_answers"] = {}

        # TODO: Get current question ID and store answer
        # For now, use placeholder
        question_id = "q1"  # TODO: Get from current question
        user_data["assessment_answers"][question_id] = answer_index

        # TODO: Check if more questions remain
        # For now, complete assessment after first answer (placeholder)
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
                await update.callback_query.edit_message_text("Assessment not found.")
            else:
                await update.message.reply_text("Assessment not found.")
            return

        user = db.query(User).filter(User.id == assessment.user_id).first()

        # TODO: Get actual questions and calculate score
        # For now, use placeholder
        questions = []  # TODO: Get from database
        answers = context.user_data.get("assessment_answers", {})

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
            "Assessment Complete!\n\n"
            f"Your English level is: {level}\n\n"
            f"Score: {score * 100:.1f}%\n\n"
            "Based on the Common European Framework of Reference (CEFR):\n"
            "- A1-A2: Beginner\n"
            "- B1-B2: Intermediate\n"
            "- C1-C2: Advanced\n\n"
            "Now you can start learning with tasks appropriate to your level!\n"
            "Type /task to get your first learning task."
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(result_message)
        else:
            await update.message.reply_text(result_message)

        # Clear assessment from context
        context.user_data.pop("current_assessment_id", None)
        context.user_data.pop("assessment_answers", None)

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
