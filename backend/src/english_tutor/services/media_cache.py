"""Media cache service for storing audio/video files locally.

This service provides caching for media files downloaded from Google Drive,
storing them in a persistent volume on Fly.io to avoid repeated downloads.
"""

import hashlib
from pathlib import Path
from typing import Optional

from src.english_tutor.config import get_settings
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)


class MediaCacheService:
    """Service for caching media files locally."""

    def __init__(self, cache_dir: Optional[str] = None) -> None:
        """Initialize media cache service.

        Args:
            cache_dir: Directory path for cache storage. If None, uses default from config.
        """
        if cache_dir is None:
            cache_dir = get_settings().media_cache_dir

        self.cache_dir = Path(cache_dir)
        self._cache_enabled = False
        self._cache_initialized = False

    def _ensure_cache_directory(self) -> None:
        """Ensure cache directory exists and is writable.

        This is called lazily on first use to avoid issues in test environments.
        If the directory cannot be created, caching is disabled but the service
        continues to work (just without caching).
        """
        if self._cache_initialized:
            return

        self._cache_initialized = True
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            # Verify write permissions
            test_file = self.cache_dir / ".test_write"
            test_file.touch()
            test_file.unlink()
            self._cache_enabled = True
            logger.info(f"Media cache directory ready: {self.cache_dir}")
        except OSError as e:
            # In test environments or read-only filesystems, disable caching
            # but allow the service to continue working
            self._cache_enabled = False
            logger.warning(
                f"Cache directory not accessible {self.cache_dir}: {e}. "
                "Caching disabled, but service will continue without cache."
            )

    def _get_cache_key(self, file_id: str) -> str:
        """Generate cache key from file ID.

        Args:
            file_id: Google Drive file ID or URL identifier

        Returns:
            Cache key (filename-safe hash)
        """
        # Use hash to create a safe filename
        hash_obj = hashlib.sha256(file_id.encode())
        return hash_obj.hexdigest()

    def _get_cache_path(self, file_id: str, extension: Optional[str] = None) -> Path:
        """Get cache file path for a file ID.

        Args:
            file_id: Google Drive file ID or URL identifier
            extension: Optional file extension (e.g., '.mp3', '.mp4')

        Returns:
            Path to cached file
        """
        cache_key = self._get_cache_key(file_id)
        if extension:
            # Ensure extension starts with dot
            if not extension.startswith("."):
                extension = f".{extension}"
            return self.cache_dir / f"{cache_key}{extension}"
        return self.cache_dir / cache_key

    def get(self, file_id: str) -> Optional[bytes]:
        """Get cached file content.

        Args:
            file_id: Google Drive file ID or URL identifier

        Returns:
            File content as bytes if cached, None otherwise
        """
        self._ensure_cache_directory()
        if not self._cache_enabled:
            return None

        # Try to find file with or without extension
        cache_path = self._get_cache_path(file_id)

        # Check exact path first
        if cache_path.exists():
            try:
                return cache_path.read_bytes()
            except OSError as e:
                logger.warning(f"Failed to read cached file {cache_path}: {e}")
                return None

        # Try common extensions
        for ext in [".mp3", ".mp4", ".wav", ".ogg", ".m4a", ".webm"]:
            ext_path = self._get_cache_path(file_id, ext)
            if ext_path.exists():
                try:
                    return ext_path.read_bytes()
                except OSError as e:
                    logger.warning(f"Failed to read cached file {ext_path}: {e}")
                    continue

        return None

    def put(self, file_id: str, content: bytes, extension: Optional[str] = None) -> Path:
        """Store file content in cache.

        Args:
            file_id: Google Drive file ID or URL identifier
            content: File content as bytes
            extension: Optional file extension (e.g., '.mp3', '.mp4')

        Returns:
            Path to cached file

        Note:
            If caching is disabled (e.g., in test environments), this is a no-op
            and returns a dummy path. No exception is raised.
        """
        self._ensure_cache_directory()
        if not self._cache_enabled:
            # Return dummy path when caching is disabled
            return self._get_cache_path(file_id, extension)

        cache_path = self._get_cache_path(file_id, extension)

        try:
            # Write to temporary file first, then rename (atomic operation)
            temp_path = cache_path.with_suffix(f"{cache_path.suffix}.tmp")
            temp_path.write_bytes(content)
            temp_path.replace(cache_path)
            logger.info(f"Cached file: {cache_path} ({len(content)} bytes)")
            return cache_path
        except OSError as e:
            # Log warning but don't fail - caching is optional
            logger.warning(f"Failed to write cache file {cache_path}: {e}")
            return cache_path

    def exists(self, file_id: str) -> bool:
        """Check if file is cached.

        Args:
            file_id: Google Drive file ID or URL identifier

        Returns:
            True if file exists in cache, False otherwise
        """
        self._ensure_cache_directory()
        if not self._cache_enabled:
            return False

        cache_path = self._get_cache_path(file_id)
        if cache_path.exists():
            return True

        # Check common extensions
        for ext in [".mp3", ".mp4", ".wav", ".ogg", ".m4a", ".webm"]:
            if self._get_cache_path(file_id, ext).exists():
                return True

        return False

    def clear(self, file_id: Optional[str] = None) -> None:
        """Clear cache entry or entire cache.

        Args:
            file_id: If provided, clear only this file. If None, clear entire cache.
        """
        self._ensure_cache_directory()
        if not self._cache_enabled:
            return

        if file_id:
            cache_path = self._get_cache_path(file_id)
            if cache_path.exists():
                cache_path.unlink()
                logger.info(f"Cleared cache entry: {cache_path}")
            # Also try extensions
            for ext in [".mp3", ".mp4", ".wav", ".ogg", ".m4a", ".webm"]:
                ext_path = self._get_cache_path(file_id, ext)
                if ext_path.exists():
                    ext_path.unlink()
        else:
            # Clear entire cache
            try:
                for cache_file in self.cache_dir.glob("*"):
                    if cache_file.is_file() and not cache_file.name.startswith("."):
                        cache_file.unlink()
                logger.info("Cleared entire media cache")
            except OSError as e:
                logger.warning(f"Failed to clear cache: {e}")

    def get_cache_size(self) -> int:
        """Get total size of cache in bytes.

        Returns:
            Total cache size in bytes
        """
        self._ensure_cache_directory()
        if not self._cache_enabled:
            return 0

        total_size = 0
        try:
            for cache_file in self.cache_dir.glob("*"):
                if cache_file.is_file() and not cache_file.name.startswith("."):
                    total_size += cache_file.stat().st_size
        except OSError as e:
            logger.warning(f"Failed to calculate cache size: {e}")
        return total_size
