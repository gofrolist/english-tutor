"""Google Sheets service for reading content.

This service reads tasks and questions from Google Sheets and converts them
to the application's data models.
"""

import csv
import io
import json
import os
from typing import Any, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.english_tutor.utils.exceptions import ContentManagementError
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)


class GoogleSheetsService:
    """Service for reading content from Google Sheets."""

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        spreadsheet_id: Optional[str] = None,
    ) -> None:
        """Initialize Google Sheets service.

        Args:
            credentials_path: Path to Google service account credentials JSON file.
                If None, reads from GOOGLE_CREDENTIALS_PATH env var.
            spreadsheet_id: Google Sheets spreadsheet ID.
                If None, reads from GOOGLE_SHEETS_ID env var.
        """
        self.credentials_path = credentials_path or os.getenv("GOOGLE_CREDENTIALS_PATH")
        self.spreadsheet_id = spreadsheet_id or os.getenv("GOOGLE_SHEETS_ID")

        if not self.credentials_path:
            raise ValueError("Google credentials path is required")
        if not self.spreadsheet_id:
            raise ValueError("Google Sheets spreadsheet ID is required")

        self.service = None
        self._initialize_service()

    def _initialize_service(self) -> None:
        """Initialize Google Sheets API service."""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
            )
            self.service = build("sheets", "v4", credentials=credentials)
            logger.info("Google Sheets service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets service: {e}")
            raise ContentManagementError(f"Failed to initialize Google Sheets: {e}") from e

    def read_tasks(self, sheet_name: str = "Tasks") -> list[dict[str, Any]]:
        """Read tasks from Google Sheets.

        Expected sheet structure (first row is header):
        - level (A1-C2)
        - type (text/audio/video)
        - title
        - content_text (for text tasks)
        - content_drive_id (Google Drive file ID for audio/video tasks)
        - explanation
        - status (draft/published)
        - row_id (for tracking updates)

        Args:
            sheet_name: Name of the sheet tab containing tasks

        Returns:
            List of task dictionaries

        Raises:
            ContentManagementError: If reading from Sheets fails
        """
        try:
            range_name = f"{sheet_name}!A:H"  # Adjust range based on columns
            result = (
                self.service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                )
                .execute()
            )
            values = result.get("values", [])

            if not values:
                logger.warning(f"No data found in sheet '{sheet_name}'")
                return []

            # First row is header
            headers = values[0]
            tasks = []

            # Expected headers (row_id first)
            expected_headers = [
                "row_id",
                "level",
                "type",
                "title",
                "content_text",
                "content_drive_id",
                "explanation",
                "status",
            ]

            # Map headers to indices
            header_map = {h.lower(): i for i, h in enumerate(headers)}

            # Validate required headers
            for expected in expected_headers:
                if expected not in header_map:
                    logger.warning(f"Missing header '{expected}' in sheet '{sheet_name}'")

            # Process rows (skip header)
            for row_idx, row in enumerate(values[1:], start=2):
                if not row or all(not cell.strip() for cell in row):
                    continue  # Skip empty rows

                try:
                    task = self._parse_task_row(row, header_map, row_idx)
                    if task:
                        tasks.append(task)
                except Exception as e:
                    logger.error(f"Error parsing row {row_idx} in sheet '{sheet_name}': {e}")
                    continue

            logger.info(f"Read {len(tasks)} tasks from sheet '{sheet_name}'")
            return tasks

        except HttpError as e:
            logger.error(f"Google Sheets API error: {e}")
            raise ContentManagementError(f"Failed to read tasks from Google Sheets: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error reading tasks: {e}")
            raise ContentManagementError(f"Failed to read tasks: {e}") from e

    def _parse_task_row(
        self,
        row: list[str],
        header_map: dict[str, int],
        row_idx: int,
    ) -> Optional[dict[str, Any]]:
        """Parse a single task row from Google Sheets.

        Args:
            row: List of cell values
            header_map: Mapping of header names to column indices
            row_idx: Row number (for error reporting)

        Returns:
            Task dictionary or None if row is invalid
        """

        def get_cell(header: str, default: str = "") -> str:
            idx = header_map.get(header, -1)
            if idx >= 0 and idx < len(row):
                return row[idx].strip()
            return default

        level = get_cell("level")
        task_type = get_cell("type")
        title = get_cell("title")
        status = get_cell("status", "draft")

        # Validate required fields
        if not level or not task_type or not title:
            logger.warning(f"Row {row_idx}: Missing required fields (level, type, or title)")
            return None

        # Validate level
        valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
        if level not in valid_levels:
            logger.warning(f"Row {row_idx}: Invalid level '{level}'")
            return None

        # Validate type
        valid_types = ["text", "audio", "video"]
        if task_type not in valid_types:
            logger.warning(f"Row {row_idx}: Invalid type '{task_type}'")
            return None

        # Validate status
        valid_statuses = ["draft", "published"]
        if status not in valid_statuses:
            status = "draft"

        # Build task dict
        task = {
            "level": level,
            "type": task_type,
            "title": title,
            "status": status,
            "explanation": get_cell("explanation"),
            "row_id": get_cell("row_id", str(row_idx)),  # Use row number if not provided
        }

        # Set content based on type
        if task_type == "text":
            content_text = get_cell("content_text")
            if not content_text:
                logger.warning(f"Row {row_idx}: Text task missing content_text")
                return None
            task["content_text"] = content_text
        elif task_type == "audio":
            drive_id = get_cell("content_drive_id")
            if not drive_id:
                logger.warning(f"Row {row_idx}: Audio task missing content_drive_id")
                return None
            task["content_audio_drive_id"] = drive_id
        elif task_type == "video":
            drive_id = get_cell("content_drive_id")
            if not drive_id:
                logger.warning(f"Row {row_idx}: Video task missing content_drive_id")
                return None
            task["content_video_drive_id"] = drive_id

        return task

    def read_questions(self, sheet_name: str = "Questions") -> list[dict[str, Any]]:
        """Read questions from Google Sheets.

        Expected sheet structure (first row is header):
        - task_row_id (matches task row_id from Tasks sheet)
        - question_text
        - answer_options (comma-separated or JSON array)
        - correct_answer (index, 0-based)
        - weight (default 1.0)
        - order (display order within task)
        - row_id (for tracking updates)

        Args:
            sheet_name: Name of the sheet tab containing questions

        Returns:
            List of question dictionaries

        Raises:
            ContentManagementError: If reading from Sheets fails
        """
        try:
            range_name = f"{sheet_name}!A:G"  # Adjust range based on columns
            result = (
                self.service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                )
                .execute()
            )
            values = result.get("values", [])

            if not values:
                logger.warning(f"No data found in sheet '{sheet_name}'")
                return []

            # First row is header
            headers = values[0]
            questions = []

            # Map headers to indices
            header_map = {h.lower(): i for i, h in enumerate(headers)}

            # Process rows (skip header)
            for row_idx, row in enumerate(values[1:], start=2):
                if not row or all(not cell.strip() for cell in row):
                    continue  # Skip empty rows

                try:
                    question = self._parse_question_row(row, header_map, row_idx)
                    if question:
                        questions.append(question)
                except Exception as e:
                    logger.error(f"Error parsing row {row_idx} in sheet '{sheet_name}': {e}")
                    continue

            logger.info(f"Read {len(questions)} questions from sheet '{sheet_name}'")
            return questions

        except HttpError as e:
            logger.error(f"Google Sheets API error: {e}")
            raise ContentManagementError(f"Failed to read questions from Google Sheets: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error reading questions: {e}")
            raise ContentManagementError(f"Failed to read questions: {e}") from e

    def _parse_question_row(
        self,
        row: list[str],
        header_map: dict[str, int],
        row_idx: int,
    ) -> Optional[dict[str, Any]]:
        """Parse a single question row from Google Sheets.

        Args:
            row: List of cell values
            header_map: Mapping of header names to column indices
            row_idx: Row number (for error reporting)

        Returns:
            Question dictionary or None if row is invalid
        """

        def get_cell(header: str, default: str = "") -> str:
            idx = header_map.get(header, -1)
            if idx >= 0 and idx < len(row):
                return row[idx].strip()
            return default

        task_row_id = get_cell("task_row_id")
        question_text = get_cell("question_text")
        answer_options_str = get_cell("answer_options")
        correct_answer_str = get_cell("correct_answer")
        weight_str = get_cell("weight", "1.0")
        order_str = get_cell("order")

        # Validate required fields
        if (
            not task_row_id
            or not question_text
            or not answer_options_str
            or not correct_answer_str
            or not order_str
        ):
            logger.warning(f"Row {row_idx}: Missing required fields")
            return None

        # Parse answer options (supports JSON, pipe-delimited, semicolon-delimited, or CSV)
        answer_options = self._parse_answer_options(answer_options_str, row_idx)
        if answer_options is None:
            return None

        if not answer_options or len(answer_options) < 2:
            logger.warning(f"Row {row_idx}: Need at least 2 answer options")
            return None

        # Parse correct answer index
        try:
            correct_answer = int(correct_answer_str)
            if correct_answer < 0 or correct_answer >= len(answer_options):
                logger.warning(f"Row {row_idx}: correct_answer index out of range")
                return None
        except ValueError:
            logger.warning(f"Row {row_idx}: Invalid correct_answer (must be integer)")
            return None

        # Parse weight
        try:
            weight = float(weight_str) if weight_str else 1.0
            if weight <= 0:
                logger.warning(f"Row {row_idx}: weight must be positive")
                return None
        except ValueError:
            logger.warning(f"Row {row_idx}: Invalid weight, using default 1.0")
            weight = 1.0

        # Parse order
        try:
            order = int(order_str)
            if order <= 0:
                logger.warning(f"Row {row_idx}: order must be positive")
                return None
        except ValueError:
            logger.warning(f"Row {row_idx}: Invalid order")
            return None

        return {
            "task_row_id": task_row_id,
            "question_text": question_text,
            "answer_options": answer_options,
            "correct_answer": correct_answer,
            "weight": weight,
            "order": order,
            "row_id": get_cell("row_id", str(row_idx)),
        }

    def _parse_answer_options(self, answer_options_str: str, row_idx: int) -> Optional[list[str]]:
        """Parse answer options from string.

        Supports multiple formats:
        1. JSON array: ["option1","option2","option3"]
        2. Pipe-delimited: option1|option2|option3 (recommended for options with commas)
        3. Semicolon-delimited: option1;option2;option3
        4. CSV format: "option1","option2","option3" (handles commas within quotes)
        5. Simple comma-separated: option1,option2,option3 (fallback, may break with commas in text)

        Args:
            answer_options_str: String containing answer options
            row_idx: Row number for error reporting

        Returns:
            List of answer options or None if parsing fails
        """
        if not answer_options_str or not answer_options_str.strip():
            return None

        answer_options_str = answer_options_str.strip()

        # Format 1: JSON array
        if answer_options_str.startswith("["):
            try:
                return json.loads(answer_options_str)
            except json.JSONDecodeError as e:
                logger.warning(f"Row {row_idx}: Invalid JSON format for answer_options: {e}")
                return None

        # Format 2: Pipe-delimited (recommended for options containing commas)
        if "|" in answer_options_str:
            options = [opt.strip() for opt in answer_options_str.split("|") if opt.strip()]
            if len(options) >= 2:
                return options

        # Format 3: Semicolon-delimited
        if ";" in answer_options_str:
            options = [opt.strip() for opt in answer_options_str.split(";") if opt.strip()]
            if len(options) >= 2:
                return options

        # Format 4: CSV format (handles quoted strings with commas)
        if '"' in answer_options_str:
            try:
                # Use CSV reader to properly handle quoted strings
                reader = csv.reader(io.StringIO(answer_options_str), quotechar='"')
                options = []
                for row in reader:
                    options.extend([opt.strip() for opt in row if opt.strip()])
                if len(options) >= 2:
                    return options
            except Exception as e:
                logger.warning(f"Row {row_idx}: Error parsing CSV format answer_options: {e}")

        # Format 5: Simple comma-separated (fallback - may break with commas in text)
        options = [opt.strip() for opt in answer_options_str.split(",") if opt.strip()]
        if len(options) >= 2:
            return options

        logger.warning(f"Row {row_idx}: Could not parse answer_options, need at least 2 options")
        return None

    def read_assessment_questions(self, sheet_name: str = "Assessment") -> list[dict[str, Any]]:
        """Read assessment questions from Google Sheets.

        Expected sheet structure (first row is header):
        - level (A1, A2, B1, B2, C1, C2)
        - question_text
        - answer_options (comma-separated or JSON array)
        - correct_answer (index, 0-based)
        - weight (default 1.0)
        - skill_type (optional: grammar, vocabulary, reading, listening)
        - row_id (for tracking updates)

        Args:
            sheet_name: Name of the sheet tab containing assessment questions

        Returns:
            List of assessment question dictionaries

        Raises:
            ContentManagementError: If reading from Sheets fails
        """
        try:
            range_name = f"{sheet_name}!A:H"  # Adjust range based on columns
            result = (
                self.service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                )
                .execute()
            )
            values = result.get("values", [])

            if not values:
                logger.warning(f"No data found in sheet '{sheet_name}'")
                return []

            # First row is header
            headers = values[0]
            questions = []

            # Expected headers (row_id first)
            expected_headers = [
                "row_id",
                "level",
                "question_text",
                "answer_options",
                "correct_answer",
                "weight",
                "skill_type",
            ]

            # Map headers to indices
            header_map = {h.lower(): i for i, h in enumerate(headers)}

            # Validate required headers
            for expected in expected_headers:
                if expected not in header_map:
                    logger.warning(f"Missing header '{expected}' in sheet '{sheet_name}'")

            # Process rows (skip header)
            for row_idx, row in enumerate(values[1:], start=2):
                if not row or all(not cell.strip() for cell in row):
                    continue  # Skip empty rows

                try:
                    question = self._parse_assessment_question_row(row, header_map, row_idx)
                    if question:
                        questions.append(question)
                except Exception as e:
                    logger.error(f"Error parsing row {row_idx} in sheet '{sheet_name}': {e}")
                    continue

            logger.info(f"Read {len(questions)} assessment questions from sheet '{sheet_name}'")
            return questions

        except HttpError as e:
            logger.error(f"Google Sheets API error: {e}")
            raise ContentManagementError(
                f"Failed to read assessment questions from Google Sheets: {e}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error reading assessment questions: {e}")
            raise ContentManagementError(f"Failed to read assessment questions: {e}") from e

    def _parse_assessment_question_row(
        self,
        row: list[str],
        header_map: dict[str, int],
        row_idx: int,
    ) -> Optional[dict[str, Any]]:
        """Parse a single assessment question row from Google Sheets.

        Args:
            row: List of cell values
            header_map: Mapping of header names to column indices
            row_idx: Row number (for error reporting)

        Returns:
            Assessment question dictionary or None if row is invalid
        """

        def get_cell(header: str, default: str = "") -> str:
            idx = header_map.get(header, -1)
            if idx >= 0 and idx < len(row):
                return row[idx].strip()
            return default

        level = get_cell("level")
        question_text = get_cell("question_text")
        answer_options_str = get_cell("answer_options")
        correct_answer_str = get_cell("correct_answer")
        weight_str = get_cell("weight", "1.0")
        skill_type = get_cell("skill_type")
        row_id = get_cell("row_id", str(row_idx))

        # Validate required fields
        if not level or not question_text or not answer_options_str or not correct_answer_str:
            logger.warning(f"Row {row_idx}: Missing required fields")
            return None

        # Validate level
        valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
        if level not in valid_levels:
            logger.warning(f"Row {row_idx}: Invalid level '{level}', must be one of {valid_levels}")
            return None

        # Parse answer options (supports JSON, pipe-delimited, semicolon-delimited, or CSV)
        answer_options = self._parse_answer_options(answer_options_str, row_idx)
        if answer_options is None:
            return None

        if not answer_options or len(answer_options) < 2:
            logger.warning(f"Row {row_idx}: Need at least 2 answer options")
            return None

        # Parse correct answer index
        try:
            correct_answer = int(correct_answer_str)
            if correct_answer < 0 or correct_answer >= len(answer_options):
                logger.warning(f"Row {row_idx}: correct_answer index out of range")
                return None
        except ValueError:
            logger.warning(f"Row {row_idx}: Invalid correct_answer (must be integer)")
            return None

        # Parse weight
        try:
            weight = float(weight_str) if weight_str else 1.0
            if weight <= 0:
                logger.warning(f"Row {row_idx}: weight must be positive")
                return None
        except ValueError:
            logger.warning(f"Row {row_idx}: Invalid weight, using default 1.0")
            weight = 1.0

        return {
            "level": level,
            "question_text": question_text,
            "answer_options": answer_options,
            "correct_answer": correct_answer,
            "weight": weight,
            "skill_type": skill_type if skill_type else None,
            "row_id": row_id,
        }
