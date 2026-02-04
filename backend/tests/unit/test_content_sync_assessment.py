"""Unit tests for content sync service - assessment question synchronization.

Tests for assessment question sync operations with mocked Google Sheets.
"""

from unittest.mock import MagicMock

import pytest

from src.english_tutor.models.assessment_question import AssessmentQuestion
from src.english_tutor.services.content_sync import ContentSyncService
from src.english_tutor.utils.exceptions import ContentManagementError


class TestContentSyncAssessment:
    """Test suite for assessment question synchronization in content sync service."""

    def test_sync_assessment_questions_creates_new(self, db_session):
        """Test that sync creates new assessment questions from Google Sheets data."""
        # Mock Google Sheets service
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = []
        mock_sheets_service.read_questions.return_value = []
        mock_sheets_service.read_assessment_questions.return_value = [
            {
                "row_id": "assessment_row_1",
                "level": "A1",
                "question_text": "What is 'apple' in English?",
                "answer_options": ["Apple", "Orange", "Banana", "Grape"],
                "correct_answer": 0,
            },
            {
                "row_id": "assessment_row_2",
                "level": "B1",
                "question_text": "Choose the correct past tense:",
                "answer_options": ["I goed", "I went", "I was go", "I have go"],
                "correct_answer": 1,
            },
        ]

        # Mock Google Drive service
        mock_drive_service = MagicMock()

        # Create sync service with mocks
        service = ContentSyncService(
            sheets_service=mock_sheets_service,
            drive_service=mock_drive_service,
        )

        # Run sync
        stats = service.sync_all(db=db_session)

        # Verify stats
        assert stats["assessment_questions_created"] == 2
        assert stats["assessment_questions_updated"] == 0
        assert stats["errors"] == 0

        # Verify assessment questions were created in database
        questions = db_session.query(AssessmentQuestion).all()
        assert len(questions) == 2

        q1 = (
            db_session.query(AssessmentQuestion)
            .filter(AssessmentQuestion.sheets_row_id == "assessment_row_1")
            .first()
        )
        assert q1 is not None
        assert q1.level == "A1"
        assert q1.question_text == "What is 'apple' in English?"
        assert q1.answer_options == ["Apple", "Orange", "Banana", "Grape"]
        assert q1.correct_answer == 0

        q2 = (
            db_session.query(AssessmentQuestion)
            .filter(AssessmentQuestion.sheets_row_id == "assessment_row_2")
            .first()
        )
        assert q2 is not None
        assert q2.level == "B1"
        assert q2.question_text == "Choose the correct past tense:"
        assert q2.correct_answer == 1

    def test_sync_assessment_questions_updates_existing(self, db_session):
        """Test that sync updates existing assessment questions when data changes."""
        # Create existing assessment question in database
        existing_question = AssessmentQuestion(
            sheets_row_id="assessment_row_existing",
            level="A2",
            question_text="Original question text",
            answer_options=["A", "B", "C"],
            correct_answer=1,
        )
        db_session.add(existing_question)
        db_session.commit()

        # Mock Google Sheets service with updated data
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = []
        mock_sheets_service.read_questions.return_value = []
        mock_sheets_service.read_assessment_questions.return_value = [
            {
                "row_id": "assessment_row_existing",
                "level": "B1",
                "question_text": "Updated question text",
                "answer_options": ["X", "Y", "Z", "W"],
                "correct_answer": 3,
            },
        ]

        # Mock Google Drive service
        mock_drive_service = MagicMock()

        # Create sync service with mocks
        service = ContentSyncService(
            sheets_service=mock_sheets_service,
            drive_service=mock_drive_service,
        )

        # Run sync
        stats = service.sync_all(db=db_session)

        # Verify stats - should update, not create
        assert stats["assessment_questions_created"] == 0
        assert stats["assessment_questions_updated"] == 1
        assert stats["errors"] == 0

        # Verify question was updated
        db_session.refresh(existing_question)
        assert existing_question.level == "B1"
        assert existing_question.question_text == "Updated question text"
        assert existing_question.answer_options == ["X", "Y", "Z", "W"]
        assert existing_question.correct_answer == 3

    def test_sync_assessment_questions_skips_unchanged(self, db_session):
        """Test that sync skips assessment questions when data has not changed."""
        # Create existing assessment question in database
        existing_question = AssessmentQuestion(
            sheets_row_id="assessment_row_unchanged",
            level="B2",
            question_text="Same question text",
            answer_options=["Same A", "Same B", "Same C"],
            correct_answer=2,
        )
        db_session.add(existing_question)
        db_session.commit()

        # Mock Google Sheets service with same data
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = []
        mock_sheets_service.read_questions.return_value = []
        mock_sheets_service.read_assessment_questions.return_value = [
            {
                "row_id": "assessment_row_unchanged",
                "level": "B2",
                "question_text": "Same question text",
                "answer_options": ["Same A", "Same B", "Same C"],
                "correct_answer": 2,
            },
        ]

        # Mock Google Drive service
        mock_drive_service = MagicMock()

        # Create sync service with mocks
        service = ContentSyncService(
            sheets_service=mock_sheets_service,
            drive_service=mock_drive_service,
        )

        # Run sync
        stats = service.sync_all(db=db_session)

        # Verify stats - should skip, not update or create
        assert stats["assessment_questions_created"] == 0
        assert stats["assessment_questions_updated"] == 0
        assert stats.get("assessment_questions_skipped", 0) == 1
        assert stats["errors"] == 0

    def test_sync_assessment_questions_handles_missing_row_id(self, db_session):
        """Test that sync skips assessment questions without row_id."""
        # Mock Google Sheets service with one valid and one missing row_id
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = []
        mock_sheets_service.read_questions.return_value = []
        mock_sheets_service.read_assessment_questions.return_value = [
            {
                # No row_id field
                "level": "A1",
                "question_text": "Question without row_id",
                "answer_options": ["A", "B"],
                "correct_answer": 0,
            },
            {
                "row_id": "valid_assessment",
                "level": "A2",
                "question_text": "Valid question",
                "answer_options": ["X", "Y"],
                "correct_answer": 1,
            },
        ]

        # Mock Google Drive service
        mock_drive_service = MagicMock()

        # Create sync service with mocks
        service = ContentSyncService(
            sheets_service=mock_sheets_service,
            drive_service=mock_drive_service,
        )

        # Run sync
        stats = service.sync_all(db=db_session)

        # Only the valid question should be created
        assert stats["assessment_questions_created"] == 1

        questions = db_session.query(AssessmentQuestion).all()
        assert len(questions) == 1
        assert questions[0].sheets_row_id == "valid_assessment"

    def test_sync_assessment_questions_mixed_create_and_update(self, db_session):
        """Test sync with mix of new and existing assessment questions."""
        # Create existing question
        existing_question = AssessmentQuestion(
            sheets_row_id="existing_assessment",
            level="A1",
            question_text="Original text",
            answer_options=["Old A", "Old B"],
            correct_answer=0,
        )
        db_session.add(existing_question)
        db_session.commit()

        # Mock Google Sheets with one existing (to update) and one new question
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = []
        mock_sheets_service.read_questions.return_value = []
        mock_sheets_service.read_assessment_questions.return_value = [
            {
                "row_id": "existing_assessment",
                "level": "A2",
                "question_text": "Updated text",
                "answer_options": ["New A", "New B", "New C"],
                "correct_answer": 2,
            },
            {
                "row_id": "new_assessment",
                "level": "B1",
                "question_text": "Brand new question",
                "answer_options": ["Fresh A", "Fresh B"],
                "correct_answer": 1,
            },
        ]

        mock_drive_service = MagicMock()

        service = ContentSyncService(
            sheets_service=mock_sheets_service,
            drive_service=mock_drive_service,
        )

        stats = service.sync_all(db=db_session)

        # One created, one updated
        assert stats["assessment_questions_created"] == 1
        assert stats["assessment_questions_updated"] == 1
        assert stats["errors"] == 0

        # Verify both questions in database
        questions = db_session.query(AssessmentQuestion).all()
        assert len(questions) == 2

        updated_q = (
            db_session.query(AssessmentQuestion)
            .filter(AssessmentQuestion.sheets_row_id == "existing_assessment")
            .first()
        )
        assert updated_q.question_text == "Updated text"
        assert updated_q.level == "A2"
        assert updated_q.correct_answer == 2

        new_q = (
            db_session.query(AssessmentQuestion)
            .filter(AssessmentQuestion.sheets_row_id == "new_assessment")
            .first()
        )
        assert new_q is not None
        assert new_q.question_text == "Brand new question"

    def test_sync_assessment_questions_handles_errors_gracefully(self, db_session):
        """Test that sync handles errors when reading assessment questions from Google Sheets."""
        # Mock Google Sheets service to raise error on read_assessment_questions
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = []
        mock_sheets_service.read_questions.return_value = []
        mock_sheets_service.read_assessment_questions.side_effect = ContentManagementError(
            "Failed to read assessment questions from Google Sheets"
        )

        # Mock Google Drive service
        mock_drive_service = MagicMock()

        # Create sync service with mocks
        service = ContentSyncService(
            sheets_service=mock_sheets_service,
            drive_service=mock_drive_service,
        )

        # Run sync and expect error
        with pytest.raises(ContentManagementError) as exc_info:
            service.sync_all(db=db_session)

        assert "Failed to read" in str(exc_info.value)

    def test_sync_assessment_questions_multiple_levels(self, db_session):
        """Test that sync correctly handles assessment questions for multiple levels."""
        # Mock Google Sheets service with questions for different levels
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = []
        mock_sheets_service.read_questions.return_value = []
        mock_sheets_service.read_assessment_questions.return_value = [
            {
                "row_id": "assessment_a1_1",
                "level": "A1",
                "question_text": "A1 Question 1",
                "answer_options": ["Option 1", "Option 2"],
                "correct_answer": 0,
            },
            {
                "row_id": "assessment_a1_2",
                "level": "A1",
                "question_text": "A1 Question 2",
                "answer_options": ["Option A", "Option B"],
                "correct_answer": 1,
            },
            {
                "row_id": "assessment_b1_1",
                "level": "B1",
                "question_text": "B1 Question 1",
                "answer_options": ["Choice X", "Choice Y", "Choice Z"],
                "correct_answer": 2,
            },
            {
                "row_id": "assessment_c1_1",
                "level": "C1",
                "question_text": "C1 Question 1",
                "answer_options": ["Advanced A", "Advanced B", "Advanced C", "Advanced D"],
                "correct_answer": 3,
            },
        ]

        # Mock Google Drive service
        mock_drive_service = MagicMock()

        # Create sync service with mocks
        service = ContentSyncService(
            sheets_service=mock_sheets_service,
            drive_service=mock_drive_service,
        )

        # Run sync
        stats = service.sync_all(db=db_session)

        # Verify stats
        assert stats["assessment_questions_created"] == 4
        assert stats["errors"] == 0

        # Verify questions by level
        a1_questions = (
            db_session.query(AssessmentQuestion).filter(AssessmentQuestion.level == "A1").all()
        )
        assert len(a1_questions) == 2

        b1_questions = (
            db_session.query(AssessmentQuestion).filter(AssessmentQuestion.level == "B1").all()
        )
        assert len(b1_questions) == 1

        c1_questions = (
            db_session.query(AssessmentQuestion).filter(AssessmentQuestion.level == "C1").all()
        )
        assert len(c1_questions) == 1
