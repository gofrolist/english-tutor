"""Unit tests for MediaCacheService.

Tests for media file caching functionality including cache operations,
directory handling, and graceful degradation in read-only environments.
"""

import tempfile
from pathlib import Path

import pytest

from src.english_tutor.config import get_settings
from src.english_tutor.services.media_cache import MediaCacheService


class TestMediaCacheService:
    """Test suite for MediaCacheService."""

    @pytest.fixture(autouse=True)
    def clear_settings_cache(self):
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    def test_init_with_custom_cache_dir(self):
        """Test initialization with custom cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            assert cache.cache_dir == Path(tmpdir)
            assert cache._cache_enabled is False
            assert cache._cache_initialized is False

    def test_init_with_default_cache_dir(self, monkeypatch):
        """Test initialization with default cache directory from env."""
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setenv("MEDIA_CACHE_DIR", tmpdir)
            cache = MediaCacheService()
            assert cache.cache_dir == Path(tmpdir)

    def test_init_without_env_var(self, monkeypatch):
        """Test initialization without MEDIA_CACHE_DIR env var."""
        monkeypatch.delenv("MEDIA_CACHE_DIR", raising=False)
        cache = MediaCacheService()
        assert cache.cache_dir == Path("/app/data/media_cache")

    def test_ensure_cache_directory_creates_directory(self):
        """Test that cache directory is created on first use."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "media_cache"
            cache = MediaCacheService(cache_dir=str(cache_dir))
            assert not cache._cache_initialized

            # Trigger directory creation
            cache._ensure_cache_directory()

            assert cache._cache_initialized
            assert cache._cache_enabled
            assert cache_dir.exists()
            assert cache_dir.is_dir()

    def test_ensure_cache_directory_handles_read_only_filesystem(self, monkeypatch):
        """Test graceful handling of read-only filesystem."""
        # Use a read-only path that will fail
        read_only_path = "/readonly/path/that/does/not/exist"
        cache = MediaCacheService(cache_dir=read_only_path)

        # Mock mkdir to raise OSError
        original_mkdir = Path.mkdir

        def mock_mkdir(self, *args, **kwargs):
            if str(self) == read_only_path:
                raise OSError(30, "Read-only file system")
            return original_mkdir(self, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", mock_mkdir)

        # Should not raise exception, just disable caching
        cache._ensure_cache_directory()

        assert cache._cache_initialized
        assert not cache._cache_enabled

    def test_ensure_cache_directory_idempotent(self):
        """Test that ensure_cache_directory is idempotent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            cache._ensure_cache_directory()
            assert cache._cache_initialized

            # Call again - should not recreate
            cache._ensure_cache_directory()
            assert cache._cache_initialized

    def test_get_cache_key(self):
        """Test cache key generation from file ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            file_id = "test-file-id-123"
            key = cache._get_cache_key(file_id)

            # Should be a hex string (SHA256 produces 64 hex chars)
            assert len(key) == 64
            assert all(c in "0123456789abcdef" for c in key)

            # Same file ID should produce same key
            assert cache._get_cache_key(file_id) == key

            # Different file ID should produce different key
            assert cache._get_cache_key("different-id") != key

    def test_get_cache_path_without_extension(self):
        """Test cache path generation without extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            file_id = "test-file-id"
            path = cache._get_cache_path(file_id)

            assert path.parent == cache.cache_dir
            assert path.name == cache._get_cache_key(file_id)
            assert path.suffix == ""

    def test_get_cache_path_with_extension(self):
        """Test cache path generation with extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            file_id = "test-file-id"
            path = cache._get_cache_path(file_id, ".mp3")

            assert path.parent == cache.cache_dir
            assert path.suffix == ".mp3"
            assert path.name.endswith(".mp3")

    def test_get_cache_path_with_extension_no_dot(self):
        """Test cache path generation with extension missing dot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            file_id = "test-file-id"
            path = cache._get_cache_path(file_id, "mp3")

            assert path.suffix == ".mp3"

    def test_get_returns_none_when_cache_disabled(self, monkeypatch):
        """Test get() returns None when cache is disabled."""
        read_only_path = "/readonly/path"
        cache = MediaCacheService(cache_dir=read_only_path)

        def mock_mkdir(self, *args, **kwargs):
            if str(self) == read_only_path:
                raise OSError(30, "Read-only file system")
            return Path.mkdir(self, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", mock_mkdir)

        result = cache.get("test-file-id")
        assert result is None

    def test_get_returns_none_when_file_not_cached(self):
        """Test get() returns None when file is not in cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            result = cache.get("non-existent-file")
            assert result is None

    def test_get_returns_cached_file(self):
        """Test get() returns cached file content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            file_id = "test-file-id"
            content = b"test audio content"

            # Cache the file
            cache.put(file_id, content)

            # Retrieve it
            result = cache.get(file_id)
            assert result == content

    def test_get_with_extension(self):
        """Test get() finds files with extensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            file_id = "test-file-id"
            content = b"test audio content"

            # Cache with extension
            cache.put(file_id, content, ".mp3")

            # Retrieve without extension - should still find it
            result = cache.get(file_id)
            assert result == content

    def test_get_handles_read_error_gracefully(self, monkeypatch):
        """Test get() handles file read errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            file_id = "test-file-id"
            content = b"test content"
            cache.put(file_id, content)

            # Mock read_bytes to raise OSError
            def mock_read_bytes(self):
                raise OSError("Permission denied")

            monkeypatch.setattr(Path, "read_bytes", mock_read_bytes)

            result = cache.get(file_id)
            assert result is None

    def test_put_creates_cache_directory(self):
        """Test put() creates cache directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "media_cache"
            cache = MediaCacheService(cache_dir=str(cache_dir))

            assert not cache_dir.exists()

            # Put should create directory
            cache.put("test-id", b"content")

            assert cache_dir.exists()

    def test_put_stores_file_content(self):
        """Test put() stores file content in cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            file_id = "test-file-id"
            content = b"test audio content"

            path = cache.put(file_id, content)

            assert path.exists()
            assert path.read_bytes() == content

    def test_put_with_extension(self):
        """Test put() stores file with extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            file_id = "test-file-id"
            content = b"test content"

            path = cache.put(file_id, content, ".mp3")

            assert path.suffix == ".mp3"
            assert path.read_bytes() == content

    def test_put_returns_dummy_path_when_cache_disabled(self, monkeypatch):
        """Test put() returns dummy path when cache is disabled."""
        read_only_path = "/readonly/path"
        cache = MediaCacheService(cache_dir=read_only_path)

        def mock_mkdir(self, *args, **kwargs):
            if str(self) == read_only_path:
                raise OSError(30, "Read-only file system")
            return Path.mkdir(self, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", mock_mkdir)

        path = cache.put("test-id", b"content")
        assert path == cache._get_cache_path("test-id")
        assert not path.exists()

    def test_put_handles_write_error_gracefully(self, monkeypatch):
        """Test put() handles write errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)

            # Mock write_bytes to raise OSError
            def mock_write_bytes(self, data):
                raise OSError("Disk full")

            monkeypatch.setattr(Path, "write_bytes", mock_write_bytes)

            # Should not raise, just return path
            path = cache.put("test-id", b"content")
            assert path == cache._get_cache_path("test-id")

    def test_exists_returns_false_when_cache_disabled(self, monkeypatch):
        """Test exists() returns False when cache is disabled."""
        read_only_path = "/readonly/path"
        cache = MediaCacheService(cache_dir=read_only_path)

        def mock_mkdir(self, *args, **kwargs):
            if str(self) == read_only_path:
                raise OSError(30, "Read-only file system")
            return Path.mkdir(self, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", mock_mkdir)

        assert cache.exists("test-id") is False

    def test_exists_returns_false_for_missing_file(self):
        """Test exists() returns False for non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            assert cache.exists("non-existent") is False

    def test_exists_returns_true_for_cached_file(self):
        """Test exists() returns True for cached file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            file_id = "test-file-id"
            cache.put(file_id, b"content")

            assert cache.exists(file_id) is True

    def test_exists_finds_file_with_extension(self):
        """Test exists() finds files with extensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            file_id = "test-file-id"
            cache.put(file_id, b"content", ".mp3")

            # Should find it even without specifying extension
            assert cache.exists(file_id) is True

    def test_clear_single_file(self):
        """Test clear() removes single cached file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            file_id = "test-file-id"
            cache.put(file_id, b"content")

            assert cache.exists(file_id) is True

            cache.clear(file_id)

            assert cache.exists(file_id) is False

    def test_clear_single_file_with_extension(self):
        """Test clear() removes file with extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            file_id = "test-file-id"
            cache.put(file_id, b"content", ".mp3")

            assert cache.exists(file_id) is True

            cache.clear(file_id)

            assert cache.exists(file_id) is False

    def test_clear_entire_cache(self):
        """Test clear() removes all cached files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)

            # Add multiple files
            cache.put("file1", b"content1")
            cache.put("file2", b"content2", ".mp3")
            cache.put("file3", b"content3", ".mp4")

            assert cache.exists("file1") is True
            assert cache.exists("file2") is True
            assert cache.exists("file3") is True

            cache.clear()

            assert cache.exists("file1") is False
            assert cache.exists("file2") is False
            assert cache.exists("file3") is False

    def test_clear_ignores_dot_files(self):
        """Test clear() ignores dot files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)

            # Create a dot file manually
            dot_file = cache.cache_dir / ".hidden"
            dot_file.write_bytes(b"hidden")

            cache.put("file1", b"content1")
            cache.clear()

            # Dot file should remain
            assert dot_file.exists()
            assert cache.exists("file1") is False

    def test_clear_handles_cache_disabled(self, monkeypatch):
        """Test clear() handles disabled cache gracefully."""
        read_only_path = "/readonly/path"
        cache = MediaCacheService(cache_dir=read_only_path)

        def mock_mkdir(self, *args, **kwargs):
            if str(self) == read_only_path:
                raise OSError(30, "Read-only file system")
            return Path.mkdir(self, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", mock_mkdir)

        # Should not raise
        cache.clear("test-id")
        cache.clear()

    def test_get_cache_size_returns_zero_when_disabled(self, monkeypatch):
        """Test get_cache_size() returns 0 when cache is disabled."""
        read_only_path = "/readonly/path"
        cache = MediaCacheService(cache_dir=read_only_path)

        def mock_mkdir(self, *args, **kwargs):
            if str(self) == read_only_path:
                raise OSError(30, "Read-only file system")
            return Path.mkdir(self, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", mock_mkdir)

        assert cache.get_cache_size() == 0

    def test_get_cache_size_calculates_total_size(self):
        """Test get_cache_size() calculates total cache size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)

            # Initially empty
            assert cache.get_cache_size() == 0

            # Add files
            cache.put("file1", b"content1")
            cache.put("file2", b"content2" * 10)  # Larger file

            size = cache.get_cache_size()
            assert size > 0
            assert size >= len(b"content1") + len(b"content2" * 10)

    def test_get_cache_size_ignores_dot_files(self):
        """Test get_cache_size() ignores dot files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)

            cache.put("file1", b"content1")

            # Create a dot file manually
            dot_file = cache.cache_dir / ".hidden"
            dot_file.write_bytes(b"hidden content")

            size = cache.get_cache_size()
            # Should only count file1, not .hidden
            assert size == len(b"content1")

    def test_get_cache_size_handles_errors_gracefully(self, monkeypatch):
        """Test get_cache_size() handles errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            cache.put("file1", b"content1")

            # Mock stat to raise OSError
            def mock_stat(self, *, follow_symlinks=True):
                raise OSError("Permission denied")

            monkeypatch.setattr(Path, "stat", mock_stat)

            # Should return 0 instead of raising
            size = cache.get_cache_size()
            assert size == 0

    def test_put_overwrites_existing_file(self):
        """Test put() overwrites existing cached file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            file_id = "test-file-id"

            # Put initial content
            cache.put(file_id, b"old content")
            assert cache.get(file_id) == b"old content"

            # Overwrite with new content
            cache.put(file_id, b"new content")
            assert cache.get(file_id) == b"new content"

    def test_clear_handles_oserror_when_clearing_all(self, monkeypatch):
        """Test clear() handles OSError when clearing entire cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCacheService(cache_dir=tmpdir)
            cache.put("file1", b"content1")

            # Mock unlink to raise OSError
            def mock_unlink(self, missing_ok=False):
                raise OSError("Permission denied")

            monkeypatch.setattr(Path, "unlink", mock_unlink)

            # Should not raise, just log warning
            cache.clear()
