"""Content management API for tasks.

REST API endpoints for managing learning tasks (CRUD operations).
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from src.english_tutor.api.dependencies import get_db
from src.english_tutor.models.task import Task, TaskStatus
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


# Pydantic models for request/response
class TaskCreate(BaseModel):
    """Task creation request model."""

    level: str = Field(..., description="English proficiency level (A1-C2)")
    type: str = Field(..., description="Content type (text, audio, video)")
    title: str = Field(..., description="Task title")
    content_text: Optional[str] = Field(None, description="Text content for text-type tasks")
    content_audio_url: Optional[str] = Field(None, description="URL for audio content")
    content_video_url: Optional[str] = Field(None, description="URL for video content")
    explanation: Optional[str] = Field(None, description="Educational explanation/rules")
    status: str = Field(default="draft", description="Task status (draft, published)")


class TaskUpdate(BaseModel):
    """Task update request model."""

    level: Optional[str] = Field(None, description="English proficiency level (A1-C2)")
    type: Optional[str] = Field(None, description="Content type (text, audio, video)")
    title: Optional[str] = Field(None, description="Task title")
    content_text: Optional[str] = Field(None, description="Text content for text-type tasks")
    content_audio_url: Optional[str] = Field(None, description="URL for audio content")
    content_video_url: Optional[str] = Field(None, description="URL for video content")
    explanation: Optional[str] = Field(None, description="Educational explanation/rules")
    status: Optional[str] = Field(None, description="Task status (draft, published)")


class TaskResponse(BaseModel):
    """Task response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    level: str
    type: str
    title: str
    content_text: Optional[str]
    content_audio_url: Optional[str]
    content_video_url: Optional[str]
    explanation: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=list[TaskResponse])
def get_tasks(
    level: Optional[str] = None,
    task_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[TaskResponse]:
    """Get list of tasks with optional filtering.

    Args:
        level: Filter by English proficiency level (A1-C2)
        task_type: Filter by content type (text, audio, video)
        status: Filter by status (draft, published)
        db: Database session

    Returns:
        List of TaskResponse objects
    """
    query = db.query(Task)

    if level:
        query = query.filter(Task.level == level)
    if task_type:
        query = query.filter(Task.type == task_type)
    if status:
        query = query.filter(Task.status == status)

    tasks = query.all()

    logger.info(
        "Tasks retrieved",
        extra={
            "count": len(tasks),
            "filters": {"level": level, "type": task_type, "status": status},
        },
    )

    return [TaskResponse.model_validate(task) for task in tasks]


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Create a new task.

    Args:
        task_data: Task creation data
        db: Database session

    Returns:
        Created TaskResponse object

    Raises:
        HTTPException: If validation fails or task creation fails
    """
    # Validate level
    valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    if task_data.level not in valid_levels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid level: {task_data.level}. Must be one of: {', '.join(valid_levels)}",
        )

    # Validate type
    valid_types = ["text", "audio", "video"]
    if task_data.type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid type: {task_data.type}. Must be one of: {', '.join(valid_types)}",
        )

    # Validate content based on type
    if task_data.type == "text" and not task_data.content_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="content_text is required for text-type tasks",
        )
    if task_data.type == "audio" and not task_data.content_audio_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="content_audio_url is required for audio-type tasks",
        )
    if task_data.type == "video" and not task_data.content_video_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="content_video_url is required for video-type tasks",
        )

    # Validate status
    valid_statuses = ["draft", "published"]
    if task_data.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {task_data.status}. Must be one of: {', '.join(valid_statuses)}",
        )

    try:
        task = Task(
            level=task_data.level,
            type=task_data.type,
            title=task_data.title,
            content_text=task_data.content_text,
            content_audio_url=task_data.content_audio_url,
            content_video_url=task_data.content_video_url,
            explanation=task_data.explanation,
            status=task_data.status,  # Status is already a string, model expects string
        )

        db.add(task)
        db.commit()
        db.refresh(task)

        logger.info(
            "Task created", extra={"task_id": str(task.id), "level": task.level, "type": task.type}
        )

        return TaskResponse.model_validate(task)
    except Exception as e:
        db.rollback()
        logger.error("Task creation failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}",
        ) from e


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: UUID,
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Get a task by ID.

    Args:
        task_id: Task UUID
        db: Database session

    Returns:
        TaskResponse object

    Raises:
        HTTPException: If task not found
    """
    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    return TaskResponse.model_validate(task)


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: UUID,
    task_data: TaskUpdate,
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Update a task.

    Args:
        task_id: Task UUID
        task_data: Task update data
        db: Database session

    Returns:
        Updated TaskResponse object

    Raises:
        HTTPException: If task not found or validation fails
    """
    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    try:
        # Update fields if provided
        if task_data.level is not None:
            valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
            if task_data.level not in valid_levels:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid level: {task_data.level}",
                )
            task.level = task_data.level

        if task_data.type is not None:
            valid_types = ["text", "audio", "video"]
            if task_data.type not in valid_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid type: {task_data.type}",
                )
            task.type = task_data.type

        if task_data.title is not None:
            task.title = task_data.title

        if task_data.content_text is not None:
            task.content_text = task_data.content_text

        if task_data.content_audio_url is not None:
            task.content_audio_url = task_data.content_audio_url

        if task_data.content_video_url is not None:
            task.content_video_url = task_data.content_video_url

        if task_data.explanation is not None:
            task.explanation = task_data.explanation

        if task_data.status is not None:
            valid_statuses = ["draft", "published"]
            if task_data.status not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {task_data.status}",
                )
            task.status = task_data.status

        db.commit()
        db.refresh(task)

        logger.info("Task updated", extra={"task_id": str(task.id)})

        return TaskResponse.model_validate(task)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Task update failed", extra={"task_id": str(task_id), "error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update task: {str(e)}",
        ) from e


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    """Delete a task.

    Args:
        task_id: Task UUID
        db: Database session

    Raises:
        HTTPException: If task not found
    """
    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    try:
        db.delete(task)
        db.commit()

        logger.info("Task deleted", extra={"task_id": str(task_id)})
    except Exception as e:
        db.rollback()
        logger.error("Task deletion failed", extra={"task_id": str(task_id), "error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete task: {str(e)}",
        ) from e


@router.post("/{task_id}/publish", response_model=TaskResponse)
def publish_task(
    task_id: UUID,
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Publish a task (change status from draft to published).

    Args:
        task_id: Task UUID
        db: Database session

    Returns:
        Updated TaskResponse object

    Raises:
        HTTPException: If task not found or already published
    """
    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    if task.status == TaskStatus.PUBLISHED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task is already published: {task_id}",
        )

    try:
        task.status = TaskStatus.PUBLISHED.value
        db.commit()
        db.refresh(task)

        logger.info("Task published", extra={"task_id": str(task.id)})

        return TaskResponse.model_validate(task)
    except Exception as e:
        db.rollback()
        logger.error("Task publish failed", extra={"task_id": str(task_id), "error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish task: {str(e)}",
        ) from e
