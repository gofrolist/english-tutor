"""Admin endpoints for cache management and system operations."""

from fastapi import APIRouter, HTTPException, status

from src.english_tutor.services.media_cache import MediaCacheService
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])

media_cache_service = MediaCacheService()


@router.delete("/cache")
async def clear_cache(file_id: str | None = None) -> dict[str, str]:
    """Clear media cache.

    Args:
        file_id: Optional file ID to clear specific file. If None, clears entire cache.

    Returns:
        Success message

    Raises:
        HTTPException: If cache clearing fails
    """
    try:
        if file_id:
            media_cache_service.clear(file_id)
            logger.info(f"Cleared cache for file: {file_id}")
            return {"status": "success", "message": f"Cache cleared for file: {file_id}"}
        else:
            media_cache_service.clear()
            logger.info("Cleared entire media cache")
            return {"status": "success", "message": "Entire media cache cleared"}
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}",
        ) from e


@router.get("/cache/size")
async def get_cache_size() -> dict[str, int | float | str]:
    """Get media cache size.

    Returns:
        Cache size in bytes and human-readable format
    """
    try:
        size_bytes = media_cache_service.get_cache_size()
        size_mb = size_bytes / (1024 * 1024)
        return {
            "size_bytes": size_bytes,
            "size_mb": round(size_mb, 2),
            "status": "success",
        }
    except Exception as e:
        logger.error(f"Failed to get cache size: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache size: {str(e)}",
        ) from e
