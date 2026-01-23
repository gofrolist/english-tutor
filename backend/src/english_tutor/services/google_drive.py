"""Google Drive service for handling media files.

This service retrieves public URLs for files stored in Google Drive.
"""

import os
from typing import Any, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.english_tutor.utils.exceptions import ContentManagementError
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)


class GoogleDriveService:
    """Service for accessing files in Google Drive."""

    def __init__(
        self,
        credentials_path: Optional[str] = None,
    ) -> None:
        """Initialize Google Drive service.

        Args:
            credentials_path: Path to Google service account credentials JSON file.
                If None, reads from GOOGLE_CREDENTIALS_PATH env var.
        """
        self.credentials_path = credentials_path or os.getenv("GOOGLE_CREDENTIALS_PATH")

        if not self.credentials_path:
            raise ValueError("Google credentials path is required")

        self.service = None
        self._initialize_service()

    def _initialize_service(self) -> None:
        """Initialize Google Drive API service."""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
            self.service = build("drive", "v3", credentials=credentials)
            logger.info("Google Drive service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")
            raise ContentManagementError(f"Failed to initialize Google Drive: {e}") from e

    def get_file_url(self, file_id: str) -> str:
        """Get public URL for a Google Drive file.

        For files to be accessible, they must be shared publicly or with the service account.

        Args:
            file_id: Google Drive file ID

        Returns:
            Public URL for the file

        Raises:
            ContentManagementError: If file access fails
        """
        try:
            # Get file metadata
            file_metadata = (
                self.service.files()
                .get(
                    fileId=file_id,
                    fields="id, name, mimeType, webViewLink, webContentLink",
                )
                .execute()
            )

            # Try to get direct download link
            if file_metadata.get("webContentLink"):
                # Remove export parameter if present for direct download
                url = file_metadata["webContentLink"]
                # For Google Docs/Sheets, we might need to export
                # For media files (audio/video), webContentLink should work
                return url

            # Fallback to web view link
            if file_metadata.get("webViewLink"):
                logger.warning(f"File {file_id} only has webViewLink, not webContentLink")
                return file_metadata["webViewLink"]

            # If neither available, construct direct download URL
            # This works for files shared publicly
            url = f"https://drive.google.com/uc?export=download&id={file_id}"
            logger.info(f"Using constructed URL for file {file_id}")
            return url

        except HttpError as e:
            logger.error(f"Google Drive API error for file {file_id}: {e}")
            raise ContentManagementError(f"Failed to get file URL: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting file URL: {e}")
            raise ContentManagementError(f"Failed to get file URL: {e}") from e

    def get_file_download_url(self, file_id: str) -> str:
        """Get direct download URL for a Google Drive file.

        This constructs a direct download URL that can be used by Telegram bot
        to send media files.

        Args:
            file_id: Google Drive file ID

        Returns:
            Direct download URL

        Note:
            The file must be shared publicly or with the service account for this to work.
        """
        # Direct download URL format
        # For large files, Google may require confirmation, so we use the export format
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    def get_file_metadata(self, file_id: str) -> dict[str, Any]:
        """Get file metadata from Google Drive.

        Args:
            file_id: Google Drive file ID

        Returns:
            File metadata dict containing at least id, name, mimeType

        Raises:
            ContentManagementError: If metadata fetch fails
        """
        try:
            return (
                self.service.files()
                .get(
                    fileId=file_id,
                    fields="id,name,mimeType,size",
                    supportsAllDrives=True,
                )
                .execute()
            )
        except HttpError as e:
            logger.error(f"Google Drive API error fetching metadata for file {file_id}: {e}")
            raise ContentManagementError(f"Failed to get file metadata: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching metadata for file {file_id}: {e}")
            raise ContentManagementError(f"Failed to get file metadata: {e}") from e

    def download_file_content(self, file_id: str) -> bytes:
        """Download file content from Google Drive as bytes.

        Args:
            file_id: Google Drive file ID

        Returns:
            File content as bytes

        Raises:
            ContentManagementError: If file download fails
        """
        try:
            request = self.service.files().get_media(fileId=file_id, supportsAllDrives=True)
            from io import BytesIO

            file_content = BytesIO()
            downloader = self._get_media_downloader(request, file_content)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.debug(f"Download progress: {int(status.progress() * 100)}%")

            return file_content.getvalue()
        except HttpError as e:
            logger.error(f"Google Drive API error downloading file {file_id}: {e}")
            raise ContentManagementError(f"Failed to download file: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error downloading file {file_id}: {e}")
            raise ContentManagementError(f"Failed to download file: {e}") from e

    def download_file(self, file_id: str) -> tuple[bytes, str, str]:
        """Download a file and return its content and metadata.

        Returns:
            (content_bytes, filename, mime_type)

        Raises:
            ContentManagementError: If download fails
        """
        metadata = self.get_file_metadata(file_id)
        content = self.download_file_content(file_id)
        name = str(metadata.get("name") or f"{file_id}")
        mime = str(metadata.get("mimeType") or "application/octet-stream")
        return content, name, mime

    def _get_media_downloader(self, request, file_content):
        """Get media downloader for Google Drive API."""
        from googleapiclient.http import MediaIoBaseDownload

        return MediaIoBaseDownload(file_content, request)

    def verify_file_access(self, file_id: str) -> bool:
        """Verify that a file is accessible.

        Args:
            file_id: Google Drive file ID

        Returns:
            True if file is accessible, False otherwise
        """
        try:
            self.service.files().get(fileId=file_id, fields="id").execute()
            return True
        except HttpError:
            return False
        except Exception:
            return False
