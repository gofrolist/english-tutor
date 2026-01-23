"""Unit tests for admin API endpoints.

Tests for cache management endpoints including clearing cache and getting cache size.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.english_tutor.api.app import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_media_cache_service():
    """Create a mock MediaCacheService."""
    mock_service = MagicMock()
    return mock_service


class TestAdminCacheEndpoints:
    """Test suite for admin cache management endpoints."""

    def test_clear_cache_entire_cache(self, client, mock_media_cache_service):
        """Test clearing entire cache."""
        with patch("src.english_tutor.api.admin.media_cache_service", mock_media_cache_service):
            response = client.delete("/admin/cache")

            assert response.status_code == 200
            assert response.json() == {
                "status": "success",
                "message": "Entire media cache cleared",
            }
            # When file_id is None, clear() is called without arguments
            mock_media_cache_service.clear.assert_called_once_with()

    def test_clear_cache_specific_file(self, client, mock_media_cache_service):
        """Test clearing cache for a specific file."""
        file_id = "test_file_123"
        with patch("src.english_tutor.api.admin.media_cache_service", mock_media_cache_service):
            response = client.delete(f"/admin/cache?file_id={file_id}")

            assert response.status_code == 200
            assert response.json() == {
                "status": "success",
                "message": f"Cache cleared for file: {file_id}",
            }
            mock_media_cache_service.clear.assert_called_once_with(file_id)

    def test_clear_cache_handles_exception(self, client, mock_media_cache_service):
        """Test that cache clearing handles exceptions gracefully."""
        mock_media_cache_service.clear.side_effect = Exception("Cache error")
        with patch("src.english_tutor.api.admin.media_cache_service", mock_media_cache_service):
            response = client.delete("/admin/cache")

            assert response.status_code == 500
            assert "Failed to clear cache" in response.json()["detail"]

    def test_get_cache_size_success(self, client, mock_media_cache_service):
        """Test getting cache size successfully."""
        mock_media_cache_service.get_cache_size.return_value = 1048576  # 1 MB in bytes
        with patch("src.english_tutor.api.admin.media_cache_service", mock_media_cache_service):
            response = client.get("/admin/cache/size")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["size_bytes"] == 1048576
            assert data["size_mb"] == 1.0
            mock_media_cache_service.get_cache_size.assert_called_once()

    def test_get_cache_size_with_different_sizes(self, client, mock_media_cache_service):
        """Test getting cache size with various sizes."""
        test_cases = [
            (0, 0.0),  # Empty cache
            (1024, 0.0),  # 1 KB (should round to 0.0 MB)
            (1048576, 1.0),  # 1 MB
            (5242880, 5.0),  # 5 MB
            (10485760, 10.0),  # 10 MB
            (15728640, 15.0),  # 15 MB
        ]

        for size_bytes, expected_mb in test_cases:
            mock_media_cache_service.get_cache_size.return_value = size_bytes
            with patch("src.english_tutor.api.admin.media_cache_service", mock_media_cache_service):
                response = client.get("/admin/cache/size")

                assert response.status_code == 200
                data = response.json()
                assert data["size_bytes"] == size_bytes
                assert data["size_mb"] == expected_mb

    def test_get_cache_size_handles_exception(self, client, mock_media_cache_service):
        """Test that getting cache size handles exceptions gracefully."""
        mock_media_cache_service.get_cache_size.side_effect = Exception("Size calculation error")
        with patch("src.english_tutor.api.admin.media_cache_service", mock_media_cache_service):
            response = client.get("/admin/cache/size")

            assert response.status_code == 500
            assert "Failed to get cache size" in response.json()["detail"]

    def test_get_cache_size_rounds_correctly(self, client, mock_media_cache_service):
        """Test that cache size is rounded to 2 decimal places."""
        # 1.5 MB = 1572864 bytes
        mock_media_cache_service.get_cache_size.return_value = 1572864
        with patch("src.english_tutor.api.admin.media_cache_service", mock_media_cache_service):
            response = client.get("/admin/cache/size")

            assert response.status_code == 200
            data = response.json()
            assert data["size_mb"] == 1.5

        # 2.34 MB = 2453667 bytes (2453667 / (1024*1024) = 2.34)
        mock_media_cache_service.get_cache_size.return_value = 2453667
        with patch("src.english_tutor.api.admin.media_cache_service", mock_media_cache_service):
            response = client.get("/admin/cache/size")

            assert response.status_code == 200
            data = response.json()
            assert data["size_mb"] == 2.34  # Rounded to 2 decimal places

        # 2.35 MB = 2464153 bytes (2464153 / (1024*1024) = 2.35)
        mock_media_cache_service.get_cache_size.return_value = 2464153
        with patch("src.english_tutor.api.admin.media_cache_service", mock_media_cache_service):
            response = client.get("/admin/cache/size")

            assert response.status_code == 200
            data = response.json()
            assert data["size_mb"] == 2.35  # Rounded to 2 decimal places
