"""Content management API for questions by ID.

REST API endpoints for managing individual questions by ID.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from src.english_tutor.api.dependencies import get_db
from src.english_tutor.models.question import Question
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/questions", tags=["questions"])


# Reuse models from questions.py (in a real app, these would be in schemas.py)
class QuestionResponse(BaseModel):
    """Question response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    question_text: str
    answer_options: list[str]
    correct_answer: int
    weight: float
    order: int
    created_at: datetime
    updated_at: datetime


class QuestionUpdate(BaseModel):
    """Question update request model."""

    question_text: Optional[str] = Field(None, description="Question text")
    answer_options: Optional[list[str]] = Field(None, description="List of answer options")
    correct_answer: Optional[int] = Field(None, description="Index of correct answer")
    weight: Optional[float] = Field(None, description="Weight for scoring")
    order: Optional[int] = Field(None, description="Display order within task")


@router.get("/{question_id}", response_model=QuestionResponse)
def get_question_by_id(
    question_id: UUID,
    db: Session = Depends(get_db),
) -> QuestionResponse:
    """Get a question by ID.

    Args:
        question_id: Question UUID
        db: Database session

    Returns:
        QuestionResponse object

    Raises:
        HTTPException: If question not found
    """
    question = db.query(Question).filter(Question.id == question_id).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question not found: {question_id}",
        )

    return QuestionResponse.model_validate(question)


@router.put("/{question_id}", response_model=QuestionResponse)
def update_question_by_id(
    question_id: UUID,
    question_data: QuestionUpdate,
    db: Session = Depends(get_db),
) -> QuestionResponse:
    """Update a question by ID.

    Args:
        question_id: Question UUID
        question_data: Question update data
        db: Database session

    Returns:
        Updated QuestionResponse object

    Raises:
        HTTPException: If question not found or validation fails
    """
    question = db.query(Question).filter(Question.id == question_id).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question not found: {question_id}",
        )

    try:
        # Update fields if provided
        if question_data.question_text is not None:
            question.question_text = question_data.question_text

        if question_data.answer_options is not None:
            if len(question_data.answer_options) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="answer_options must be a non-empty list",
                )
            question.answer_options = question_data.answer_options

        if question_data.correct_answer is not None:
            answer_options = (
                question_data.answer_options
                if question_data.answer_options
                else question.answer_options
            )
            if question_data.correct_answer < 0 or question_data.correct_answer >= len(
                answer_options
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"correct_answer index {question_data.correct_answer} is out of range",
                )
            question.correct_answer = question_data.correct_answer

        if question_data.weight is not None:
            if question_data.weight <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="weight must be positive",
                )
            question.weight = question_data.weight

        if question_data.order is not None:
            if question_data.order <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="order must be positive",
                )
            question.order = question_data.order

        db.commit()
        db.refresh(question)

        logger.info("Question updated by ID", extra={"question_id": str(question.id)})

        return QuestionResponse.model_validate(question)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(
            "Question update failed",
            extra={"question_id": str(question_id), "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update question: {str(e)}",
        ) from e


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question_by_id(
    question_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    """Delete a question by ID.

    Args:
        question_id: Question UUID
        db: Database session

    Raises:
        HTTPException: If question not found
    """
    question = db.query(Question).filter(Question.id == question_id).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question not found: {question_id}",
        )

    try:
        db.delete(question)
        db.commit()

        logger.info("Question deleted by ID", extra={"question_id": str(question_id)})
    except Exception as e:
        db.rollback()
        logger.error(
            "Question deletion failed",
            extra={"question_id": str(question_id), "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete question: {str(e)}",
        ) from e
