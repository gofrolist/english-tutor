"""Content sync API endpoints.

Provides endpoints for triggering content synchronization from Google Sheets/Drive.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.english_tutor.api.dependencies import get_db
from src.english_tutor.services.content_sync import ContentSyncService
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])


class SyncResponse(BaseModel):
    """Response model for sync operation."""

    success: bool
    tasks_created: int
    tasks_updated: int
    tasks_deleted: int
    questions_created: int
    questions_updated: int
    questions_deleted: int
    errors: int
    message: str


@router.post("", response_model=SyncResponse)
def sync_content(db: Session = Depends(get_db)) -> SyncResponse:
    """Trigger content synchronization from Google Sheets/Drive.

    This endpoint reads tasks and questions from Google Sheets, resolves
    media files from Google Drive, and syncs them to the database.

    Args:
        db: Database session

    Returns:
        SyncResponse with statistics

    Raises:
        HTTPException: If sync fails
    """
    try:
        logger.info("Manual content sync triggered via API")
        sync_service = ContentSyncService()
        stats = sync_service.sync_all(db=db)

        return SyncResponse(
            success=stats["errors"] == 0,
            tasks_created=stats["tasks_created"],
            tasks_updated=stats["tasks_updated"],
            tasks_deleted=stats["tasks_deleted"],
            questions_created=stats["questions_created"],
            questions_updated=stats["questions_updated"],
            questions_deleted=stats["questions_deleted"],
            errors=stats["errors"],
            message="Content sync completed successfully"
            if stats["errors"] == 0
            else "Content sync completed with errors",
        )

    except Exception as e:
        logger.error(f"Content sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Content sync failed: {str(e)}",
        ) from e
