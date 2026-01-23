#!/usr/bin/env python3
"""Debug script to test Google Drive file access.

This script helps diagnose why a Google Drive file cannot be accessed.
It tests various scenarios and provides detailed diagnostics.
"""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.english_tutor.services.google_drive import GoogleDriveService
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)

# #region agent log
log_path = Path("/Users/evgenii.vasilenko/gofrolist/english-tutor/.cursor/debug.log")
# #endregion


def log_debug(hypothesis_id: str, message: str, data: dict):
    """Write debug log entry."""
    # #region agent log
    try:
        with open(log_path, "a") as f:
            entry = {
                "sessionId": "debug-drive-file",
                "runId": "run1",
                "hypothesisId": hypothesis_id,
                "location": "debug_drive_file.py",
                "message": message,
                "data": data,
                "timestamp": int(__import__("time").time() * 1000),
            }
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
    # #endregion
    print(f"[{hypothesis_id}] {message}: {json.dumps(data, default=str)}")


def get_service_account_email(credentials_path: str) -> str:
    """Extract service account email from credentials file."""
    # #region agent log
    log_debug("D", "Reading credentials file", {"path": credentials_path})
    # #endregion
    try:
        with open(credentials_path) as f:
            creds = json.load(f)
            email = creds.get("client_email", "")
            # #region agent log
            log_debug("D", "Service account email extracted", {"email": email})
            # #endregion
            return email
    except Exception as e:
        # #region agent log
        log_debug("D", "Failed to read credentials", {"error": str(e)})
        # #endregion
        return ""


def test_file_access(file_id: str, credentials_path: str):
    """Test Google Drive file access with detailed diagnostics."""
    print(f"\n{'=' * 60}")
    print("Testing Google Drive File Access")
    print(f"{'=' * 60}")
    print(f"File ID: {file_id}")
    print(f"Credentials: {credentials_path}\n")

    # Initialize service first
    print("\n[INITIALIZATION] Setting up Google Drive service...")
    try:
        drive_service = GoogleDriveService(credentials_path=credentials_path)
        # #region agent log
        log_debug("A", "GoogleDriveService initialized", {"success": True})
        # #endregion
        print("✓ Service initialized successfully")
    except Exception as e:
        # #region agent log
        log_debug("A", "Service initialization failed", {"error": str(e)})
        # #endregion
        print(f"✗ Failed to initialize service: {e}")
        print("\n⚠ Cannot continue diagnostics without service initialization")
        return

    # Hypothesis A: File doesn't exist
    # #region agent log
    log_debug("A", "Testing if file exists", {"file_id": file_id})
    # #endregion
    print("\n[HYPOTHESIS A] Testing if file exists...")
    try:
        metadata = drive_service.get_file_metadata(file_id)
        # #region agent log
        log_debug(
            "A",
            "File metadata retrieved",
            {
                "file_id": file_id,
                "name": metadata.get("name"),
                "mimeType": metadata.get("mimeType"),
                "size": metadata.get("size"),
            },
        )
        # #endregion
        print("✓ File EXISTS")
        print(f"  Name: {metadata.get('name')}")
        print(f"  MIME Type: {metadata.get('mimeType')}")
        print(f"  Size: {metadata.get('size')} bytes")
        print("  Status: CONFIRMED - File exists")
    except HttpError as e:
        error_details = str(e)
        # #region agent log
        log_debug(
            "A",
            "File metadata failed",
            {"error": error_details, "status_code": e.resp.status if hasattr(e, "resp") else None},
        )
        # #endregion
        if hasattr(e, "resp") and e.resp.status == 404:
            print("✗ File NOT FOUND (404)")
            print(f"  Error: {error_details}")
            print("  Status: CONFIRMED - File does not exist or is inaccessible")
            print("\n⚠ This usually means:")
            print("  1. File was deleted or moved")
            print("  2. File is not shared with the service account")
            print("  3. File ID is incorrect")
        else:
            print(f"✗ Error accessing file: {e.resp.status if hasattr(e, 'resp') else 'unknown'}")
            print(f"  Error: {error_details}")
    except Exception as e:
        # #region agent log
        log_debug("A", "Unexpected error testing file", {"error": str(e)})
        # #endregion
        print(f"✗ Unexpected error: {e}")

    # Hypothesis B: Service account doesn't have access
    # #region agent log
    log_debug("B", "Testing service account access", {"file_id": file_id})
    # #endregion
    print("\n[HYPOTHESIS B] Testing service account permissions...")
    service_account_email = get_service_account_email(credentials_path)
    if service_account_email:
        print(f"  Service Account Email: {service_account_email}")
        print("  ⚠ ACTION REQUIRED: Share the file with this email address")
        print("    1. Open Google Drive")
        print("    2. Right-click the file → 'Share'")
        print(f"    3. Add: {service_account_email}")
        print("    4. Give 'Viewer' access")
    else:
        print("  ⚠ Could not extract service account email from credentials")

    # Hypothesis C: Testing with different API parameters
    # #region agent log
    log_debug("C", "Testing with supportsAllDrives parameter", {"file_id": file_id})
    # #endregion
    print("\n[HYPOTHESIS C] Testing shared drive access...")
    try:
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        service = build("drive", "v3", credentials=credentials)

        # Test without supportsAllDrives
        try:
            result = service.files().get(fileId=file_id, fields="id,name").execute()
            # #region agent log
            log_debug(
                "C",
                "File access without supportsAllDrives",
                {"success": True, "name": result.get("name")},
            )
            # #endregion
            print("  ✓ Accessible without supportsAllDrives")
        except HttpError as e1:
            # #region agent log
            log_debug(
                "C",
                "File access without supportsAllDrives failed",
                {"error": str(e1), "status": e1.resp.status},
            )
            # #endregion
            print(f"  ✗ Not accessible without supportsAllDrives: {e1.resp.status}")

        # Test with supportsAllDrives
        try:
            result = (
                service.files()
                .get(fileId=file_id, fields="id,name", supportsAllDrives=True)
                .execute()
            )
            # #region agent log
            log_debug(
                "C",
                "File access with supportsAllDrives",
                {"success": True, "name": result.get("name")},
            )
            # #endregion
            print("  ✓ Accessible with supportsAllDrives=True")
        except HttpError as e2:
            # #region agent log
            log_debug(
                "C",
                "File access with supportsAllDrives failed",
                {"error": str(e2), "status": e2.resp.status},
            )
            # #endregion
            print(f"  ✗ Not accessible with supportsAllDrives=True: {e2.resp.status}")

    except Exception as e:
        # #region agent log
        log_debug("C", "Shared drive test failed", {"error": str(e)})
        # #endregion
        print(f"  ✗ Error testing shared drive access: {e}")

    # Hypothesis D: Test credentials validity
    # #region agent log
    log_debug("D", "Testing credentials validity", {})
    # #endregion
    print("\n[HYPOTHESIS D] Testing credentials validity...")
    try:
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        # Try to list files (this validates credentials)
        service = build("drive", "v3", credentials=credentials)
        result = service.files().list(pageSize=1, fields="files(id,name)").execute()
        # #region agent log
        log_debug("D", "Credentials are valid", {"files_count": len(result.get("files", []))})
        # #endregion
        print("  ✓ Credentials are VALID")
        print(f"  Can list files: {len(result.get('files', []))} file(s) found")
    except Exception as e:
        # #region agent log
        log_debug("D", "Credentials validation failed", {"error": str(e)})
        # #endregion
        print(f"  ✗ Credentials are INVALID or expired: {e}")
        print("  Status: CONFIRMED - Credentials issue")

    # Hypothesis E: Test file ID extraction
    # #region agent log
    log_debug("E", "Testing file ID format", {"file_id": file_id, "length": len(file_id)})
    # #endregion
    print("\n[HYPOTHESIS E] Validating file ID format...")
    if len(file_id) < 20 or len(file_id) > 50:
        print(f"  ⚠ File ID length unusual: {len(file_id)} characters")
        print("  Expected: 20-50 characters")
    else:
        print(f"  ✓ File ID length OK: {len(file_id)} characters")
    if not all(c.isalnum() or c in "-_" for c in file_id):
        print("  ⚠ File ID contains invalid characters")
    else:
        print("  ✓ File ID format valid")

    # Hypothesis F: Test download capability
    # #region agent log
    log_debug("F", "Testing file download", {"file_id": file_id})
    # #endregion
    print("\n[HYPOTHESIS F] Testing file download...")
    try:
        content, name, mime = drive_service.download_file(file_id)
        # #region agent log
        log_debug(
            "F",
            "File download successful",
            {"file_id": file_id, "name": name, "mime": mime, "size_bytes": len(content)},
        )
        # #endregion
        print("  ✓ Download SUCCESSFUL")
        print(f"  Filename: {name}")
        print(f"  MIME Type: {mime}")
        print(f"  Size: {len(content)} bytes")
        print("  Status: CONFIRMED - File is fully accessible")
    except Exception as e:
        # #region agent log
        log_debug("F", "File download failed", {"error": str(e)})
        # #endregion
        print(f"  ✗ Download FAILED: {e}")
        print("  Status: CONFIRMED - Cannot download file")

    print(f"\n{'=' * 60}")
    print("Diagnostics complete")
    print(f"{'=' * 60}\n")


def find_credentials_file() -> str | None:
    """Try to find credentials file in common locations."""
    script_dir = Path(__file__).parent
    backend_dir = script_dir.parent
    possible_paths = [
        os.getenv("GOOGLE_CREDENTIALS_PATH"),
        str(backend_dir / "credentials.json"),
        str(script_dir / "credentials.json"),
        "./credentials.json",
        "credentials.json",
    ]
    for path in possible_paths:
        if path and os.path.exists(path):
            return path
    return None


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python debug_drive_file.py <file_id> [credentials_path]")
        print("\nExample:")
        print("  python debug_drive_file.py 1LGRYdd1cLNZEp7PaxuhT4GPxbk73daLz")
        print("  python debug_drive_file.py 1LGRYdd1cLNZEp7PaxuhT4GPxbk73daLz ./credentials.json")
        sys.exit(1)

    file_id = sys.argv[1]
    credentials_path = sys.argv[2] if len(sys.argv) > 2 else None

    # Try to find credentials if not provided
    if not credentials_path:
        credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
        if not credentials_path:
            credentials_path = find_credentials_file()
            if credentials_path:
                print(f"Found credentials file: {credentials_path}")

    if not credentials_path:
        print("ERROR: Could not find credentials file")
        print("\nPlease either:")
        print("  1. Set GOOGLE_CREDENTIALS_PATH environment variable")
        print("  2. Pass credentials path as second argument")
        print("  3. Place credentials.json in backend/ directory")
        sys.exit(1)

    if not os.path.exists(credentials_path):
        print(f"ERROR: Credentials file not found: {credentials_path}")
        sys.exit(1)

    test_file_access(file_id, credentials_path)


if __name__ == "__main__":
    main()
