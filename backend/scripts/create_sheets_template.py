#!/usr/bin/env python3
"""Create a template Google Sheet with the correct structure for English Tutor.

This script creates a new Google Sheet with Tasks and Questions sheets
configured with the correct headers and example data.
"""

import json
import sys
from pathlib import Path

try:
    from google.auth import default as default_credentials
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("ERROR: Google API libraries not installed.")
    print("Please run: uv sync")
    sys.exit(1)


def create_template_sheet(
    credentials_path: str, service_account_email: str, use_user_credentials: bool = True
) -> str:
    """Create a template Google Sheet with Tasks and Questions sheets.

    Args:
        credentials_path: Path to service account credentials JSON file.
        service_account_email: Service account email for sharing.
        use_user_credentials: If True, use user's application-default credentials
            to create the sheet (recommended). If False, use service account.

    Returns:
        Spreadsheet ID of the created sheet.

    Raises:
        Exception: If sheet creation fails.
    """
    # Use user's credentials to create the sheet (they have permission)
    # Then share it with the service account
    if use_user_credentials:
        try:
            # Try to use application-default credentials (user's credentials)
            required_scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]

            try:
                # Get default credentials with required scopes
                adc_creds, project = default_credentials(scopes=required_scopes)

                # Refresh if needed
                if not adc_creds.valid:
                    from google.auth.transport.requests import Request

                    adc_creds.refresh(Request())

                credentials = adc_creds
                print("✓ Using your Google Cloud credentials to create spreadsheet")
            except Exception as e:
                print(
                    "WARNING: Application-default credentials need re-authentication with Sheets/Drive scopes"
                )
                print(f"Error: {e}")
                print("\nPlease run:")
                print(
                    "  gcloud auth application-default login --scopes=https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/cloud-platform"
                )
                print("  gcloud auth application-default set-quota-project english-tutor-484322")
                print(
                    "\nOr we can try using service account (may not have permission to create)..."
                )
                raise
        except Exception as e:
            print(f"WARNING: Could not use application-default credentials: {e}")
            print("Falling back to service account credentials...")
            # Fall back to service account
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive",
                ],
            )
    else:
        # Use service account directly
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )

    sheets_service = build("sheets", "v4", credentials=credentials)
    drive_service = build("drive", "v3", credentials=credentials)

    # Create spreadsheet
    spreadsheet = {
        "properties": {
            "title": "English Tutor - Content Template",
        },
        "sheets": [
            {
                "properties": {
                    "title": "Tasks",
                    "gridProperties": {"rowCount": 1000, "columnCount": 9},
                },
            },
            {
                "properties": {
                    "title": "Questions",
                    "gridProperties": {"rowCount": 1000, "columnCount": 7},
                },
            },
            {
                "properties": {
                    "title": "Assessment",
                    "gridProperties": {"rowCount": 1000, "columnCount": 7},
                },
            },
        ],
    }

    try:
        spreadsheet = sheets_service.spreadsheets().create(body=spreadsheet).execute()
        spreadsheet_id = spreadsheet["spreadsheetId"]
        print(f"✓ Created spreadsheet: {spreadsheet_id}")
        print(f"  URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")
    except HttpError as e:
        print(f"ERROR: Failed to create spreadsheet: {e}")
        raise

    # Define headers and example data
    tasks_headers = [
        "row_id",
        "level",
        "type",
        "title",
        "content_text",
        "content_drive_id",
        "explanation",
        "status",
    ]

    tasks_example = [
        [
            "task-001",
            "A1",
            "text",
            "Simple Present Introduction",
            "The simple present tense is used to describe habits, facts, and general truths.",
            "",
            "Use simple present for routines and facts.",
            "published",
        ],
        [
            "task-002",
            "A1",
            "audio",
            "Listening Practice - Greetings",
            "",
            "YOUR_AUDIO_FILE_ID_HERE",
            "Practice common greetings in English.",
            "published",
        ],
    ]

    questions_headers = [
        "row_id",
        "task_row_id",
        "question_text",
        "answer_options",
        "correct_answer",
        "weight",
        "order",
    ]

    questions_example = [
        [
            "question-001",
            "task-001",
            "What is the simple present form of 'to be' for 'I'?",
            "am|is|are",
            "0",
            "1.0",
            "1",
        ],
        [
            "question-002",
            "task-001",
            "Which sentence is correct?",
            "I am student,I is student,I are student",
            "0",
            "1.0",
            "2",
        ],
    ]

    # Write Tasks sheet
    try:
        # Headers
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Tasks!A1:H1",
            valueInputOption="RAW",
            body={"values": [tasks_headers]},
        ).execute()

        # Format headers (bold)
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": spreadsheet["sheets"][0]["properties"]["sheetId"],
                                "startRowIndex": 0,
                                "endRowIndex": 1,
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "textFormat": {"bold": True},
                                    "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                                }
                            },
                            "fields": "userEnteredFormat(textFormat,backgroundColor)",
                        }
                    }
                ]
            },
        ).execute()

        # Example data
        if tasks_example:
            sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range="Tasks!A2:H3",
                valueInputOption="RAW",
                body={"values": tasks_example},
            ).execute()

        print("✓ Configured 'Tasks' sheet with headers and examples")
    except HttpError as e:
        print(f"WARNING: Failed to configure Tasks sheet: {e}")

    # Write Questions sheet
    try:
        # Headers
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Questions!A1:G1",
            valueInputOption="RAW",
            body={"values": [questions_headers]},
        ).execute()

        # Format headers (bold)
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": spreadsheet["sheets"][1]["properties"]["sheetId"],
                                "startRowIndex": 0,
                                "endRowIndex": 1,
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "textFormat": {"bold": True},
                                    "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                                }
                            },
                            "fields": "userEnteredFormat(textFormat,backgroundColor)",
                        }
                    }
                ]
            },
        ).execute()

        # Example data
        if questions_example:
            sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range="Questions!A2:G3",
                valueInputOption="RAW",
                body={"values": questions_example},
            ).execute()

        print("✓ Configured 'Questions' sheet with headers and examples")
    except HttpError as e:
        print(f"WARNING: Failed to configure Questions sheet: {e}")

    # Write Assessment sheet
    assessment_headers = [
        "row_id",
        "level",
        "question_text",
        "answer_options",
        "correct_answer",
        "weight",
        "skill_type",
    ]

    assessment_example = [
        [
            "assess-001",
            "A1",
            "What is 'hello' in English?",
            "hi|hello|goodbye|thanks",
            "1",
            "1.0",
            "vocabulary",
        ],
        [
            "assess-002",
            "A1",
            "I ___ a student.",
            "am,is,are,be",
            "0",
            "1.0",
            "grammar",
        ],
        [
            "assess-003",
            "A2",
            "She ___ to work every day.",
            "go,goes,going,went",
            "1",
            "1.0",
            "grammar",
        ],
        [
            "assess-004",
            "B1",
            "Choose the correct past tense: Yesterday I ___ to the store.",
            "go,went,gone,going",
            "1",
            "1.5",
            "grammar",
        ],
    ]

    try:
        # Headers
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Assessment!A1:G1",
            valueInputOption="RAW",
            body={"values": [assessment_headers]},
        ).execute()

        # Format headers (bold)
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": spreadsheet["sheets"][2]["properties"]["sheetId"],
                                "startRowIndex": 0,
                                "endRowIndex": 1,
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "textFormat": {"bold": True},
                                    "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                                }
                            },
                            "fields": "userEnteredFormat(textFormat,backgroundColor)",
                        }
                    }
                ]
            },
        ).execute()

        # Example data
        if assessment_example:
            sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range="Assessment!A2:G5",
                valueInputOption="RAW",
                body={"values": assessment_example},
            ).execute()

        print("✓ Configured 'Assessment' sheet with headers and examples")
    except HttpError as e:
        print(f"WARNING: Failed to configure Assessment sheet: {e}")

    # Share with service account (required for the service account to read it)
    try:
        # Check if already shared
        permissions = drive_service.permissions().list(fileId=spreadsheet_id).execute()
        already_shared = any(
            perm.get("emailAddress") == service_account_email
            for perm in permissions.get("permissions", [])
        )

        if not already_shared:
            drive_service.permissions().create(
                fileId=spreadsheet_id,
                body={
                    "type": "user",
                    "role": "reader",  # Service account only needs read access
                    "emailAddress": service_account_email,
                },
                fields="id",
            ).execute()
            print(f"✓ Shared spreadsheet with service account: {service_account_email}")
        else:
            print(f"✓ Spreadsheet already shared with service account: {service_account_email}")
    except HttpError as e:
        # Log but don't fail - user can share manually
        print(f"WARNING: Could not automatically share with service account: {e}")
        print(f"Please manually share the spreadsheet with: {service_account_email}")

    return spreadsheet_id


def main() -> None:
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: create_sheets_template.py <credentials_path> [service_account_email]")
        sys.exit(1)

    credentials_path = sys.argv[1]

    # Get service account email from credentials if not provided
    if len(sys.argv) >= 3:
        service_account_email = sys.argv[2]
    else:
        # Read from credentials file
        with open(credentials_path) as f:
            creds_data = json.load(f)
            service_account_email = creds_data.get("client_email", "")
            if not service_account_email:
                print("ERROR: Could not find service account email in credentials file")
                sys.exit(1)

    if not Path(credentials_path).exists():
        print(f"ERROR: Credentials file not found: {credentials_path}")
        sys.exit(1)

    try:
        spreadsheet_id = create_template_sheet(credentials_path, service_account_email)
        print("\n✓ Template spreadsheet created successfully!")
        print(f"\nSpreadsheet ID: {spreadsheet_id}")
        print(f"URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")
        print("\nNext steps:")
        print("1. Open the spreadsheet and review the template")
        print("2. Replace example data with your content")
        print("3. For audio/video tasks, upload files to Google Drive and add their file IDs")
        print("4. Share your Google Drive files with the service account email")
    except Exception as e:
        print(f"\nERROR: Failed to create template: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
