"""Unit tests for content sync service - question synchronization.

Tests for question sync operations with mocked Google Sheets.
"""

from unittest.mock import MagicMock

import pytest

from src.english_tutor.models.question import Question
from src.english_tutor.models.task import Task, TaskStatus
from src.english_tutor.services.content_sync import ContentSyncService
from src.english_tutor.utils.exceptions import ContentManagementError


class TestContentSyncQuestions:
    """Test suite for question synchronization in content sync service."""

    def _create_task(self, db_session, sheets_row_id: str = "task_row_1") -> Task:
        """Helper to create a task for question tests.

        Args:
            db_session: Database session
            sheets_row_id: Google Sheets row ID for the task

        Returns:
            Created Task instance
        """
        task = Task(
            sheets_row_id=sheets_row_id,
            level="B1",
            type="text",
            title="Test Task",
            content_text="Task content for learning",
            language_domain="grammar",
            status=TaskStatus.PUBLISHED,
        )
        db_session.add(task)
        db_session.commit()
        return task

    def test_sync_questions_creates_new(self, db_session):
        """Test that sync creates new questions from Google Sheets data."""
        # Create a task that questions will belong to
        task = self._create_task(db_session)

        # Mock Google Sheets service
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = [
            {
                "row_id": task.sheets_row_id,
                "level": "B1",
                "type": "text",
                "title": "Test Task",
                "content_text": "Task content for learning",
                "language_domain": "grammar",
                "status": "published",
            },
        ]
        mock_sheets_service.read_questions.return_value = [
            {
                "row_id": "question_row_1",
                "task_row_id": task.sheets_row_id,
                "question_text": "What is the correct form?",
                "answer_options": ["Option A", "Option B", "Option C", "Option D"],
                "correct_answer": 0,
            },
            {
                "row_id": "question_row_2",
                "task_row_id": task.sheets_row_id,
                "question_text": "Choose the best answer:",
                "answer_options": ["First", "Second", "Third"],
                "correct_answer": 2,
            },
        ]
        mock_sheets_service.read_assessment_questions.return_value = []

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
        assert stats["questions_created"] == 2
        assert stats["questions_updated"] == 0
        assert stats["errors"] == 0

        # Verify questions were created in database
        questions = db_session.query(Question).all()
        assert len(questions) == 2

        q1 = db_session.query(Question).filter(Question.sheets_row_id == "question_row_1").first()
        assert q1 is not None
        assert q1.task_id == task.sheets_row_id
        assert q1.question_text == "What is the correct form?"
        assert q1.answer_options == ["Option A", "Option B", "Option C", "Option D"]
        assert q1.correct_answer == 0

        q2 = db_session.query(Question).filter(Question.sheets_row_id == "question_row_2").first()
        assert q2 is not None
        assert q2.task_id == task.sheets_row_id
        assert q2.question_text == "Choose the best answer:"
        assert q2.correct_answer == 2

    def test_sync_questions_updates_existing(self, db_session):
        """Test that sync updates existing questions when data changes."""
        # Create task and existing question
        task = self._create_task(db_session)
        existing_question = Question(
            sheets_row_id="question_row_existing",
            task_id=task.sheets_row_id,
            question_text="Original question text",
            answer_options=["A", "B", "C"],
            correct_answer=1,
        )
        db_session.add(existing_question)
        db_session.commit()

        # Mock Google Sheets service with updated question data
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = [
            {
                "row_id": task.sheets_row_id,
                "level": "B1",
                "type": "text",
                "title": "Test Task",
                "content_text": "Task content for learning",
                "language_domain": "grammar",
                "status": "published",
            },
        ]
        mock_sheets_service.read_questions.return_value = [
            {
                "row_id": "question_row_existing",
                "task_row_id": task.sheets_row_id,
                "question_text": "Updated question text",
                "answer_options": ["X", "Y", "Z", "W"],
                "correct_answer": 3,
            },
        ]
        mock_sheets_service.read_assessment_questions.return_value = []

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
        assert stats["questions_created"] == 0
        assert stats["questions_updated"] == 1
        assert stats["errors"] == 0

        # Verify question was updated
        db_session.refresh(existing_question)
        assert existing_question.question_text == "Updated question text"
        assert existing_question.answer_options == ["X", "Y", "Z", "W"]
        assert existing_question.correct_answer == 3

    def test_sync_questions_skips_unchanged(self, db_session):
        """Test that sync skips questions when data has not changed."""
        # Create task and existing question
        task = self._create_task(db_session)
        existing_question = Question(
            sheets_row_id="question_row_unchanged",
            task_id=task.sheets_row_id,
            question_text="Same question text",
            answer_options=["Same A", "Same B", "Same C"],
            correct_answer=1,
        )
        db_session.add(existing_question)
        db_session.commit()

        # Mock Google Sheets service with same data
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = [
            {
                "row_id": task.sheets_row_id,
                "level": "B1",
                "type": "text",
                "title": "Test Task",
                "content_text": "Task content for learning",
                "language_domain": "grammar",
                "status": "published",
            },
        ]
        mock_sheets_service.read_questions.return_value = [
            {
                "row_id": "question_row_unchanged",
                "task_row_id": task.sheets_row_id,
                "question_text": "Same question text",
                "answer_options": ["Same A", "Same B", "Same C"],
                "correct_answer": 1,
            },
        ]
        mock_sheets_service.read_assessment_questions.return_value = []

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
        assert stats["questions_created"] == 0
        assert stats["questions_updated"] == 0
        assert stats.get("questions_skipped", 0) == 1
        assert stats["errors"] == 0

    def test_sync_questions_handles_missing_task(self, db_session):
        """Test that sync handles questions for non-existent tasks gracefully."""
        # Don't create a task - questions will reference non-existent task

        # Mock Google Sheets service
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = []  # No tasks
        mock_sheets_service.read_questions.return_value = [
            {
                "row_id": "orphan_question_1",
                "task_row_id": "non_existent_task",
                "question_text": "Orphan question",
                "answer_options": ["A", "B"],
                "correct_answer": 0,
            },
        ]
        mock_sheets_service.read_assessment_questions.return_value = []

        # Mock Google Drive service
        mock_drive_service = MagicMock()

        # Create sync service with mocks
        service = ContentSyncService(
            sheets_service=mock_sheets_service,
            drive_service=mock_drive_service,
        )

        # Run sync - should not raise, questions for missing tasks are skipped
        stats = service.sync_all(db=db_session)

        # Orphan question should not be created
        assert stats["questions_created"] == 0
        questions = db_session.query(Question).all()
        assert len(questions) == 0

    def test_sync_questions_multiple_tasks(self, db_session):
        """Test that sync correctly assigns questions to multiple tasks."""
        # Create two tasks
        task1 = Task(
            sheets_row_id="task_row_1",
            level="A2",
            type="text",
            title="Task One",
            content_text="Content one",
            status=TaskStatus.PUBLISHED,
        )
        task2 = Task(
            sheets_row_id="task_row_2",
            level="B1",
            type="text",
            title="Task Two",
            content_text="Content two",
            status=TaskStatus.PUBLISHED,
        )
        db_session.add_all([task1, task2])
        db_session.commit()

        # Mock Google Sheets service
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = [
            {
                "row_id": "task_row_1",
                "level": "A2",
                "type": "text",
                "title": "Task One",
                "content_text": "Content one",
                "status": "published",
            },
            {
                "row_id": "task_row_2",
                "level": "B1",
                "type": "text",
                "title": "Task Two",
                "content_text": "Content two",
                "status": "published",
            },
        ]
        mock_sheets_service.read_questions.return_value = [
            {
                "row_id": "q1_for_task1",
                "task_row_id": "task_row_1",
                "question_text": "Question for task 1",
                "answer_options": ["A", "B"],
                "correct_answer": 0,
            },
            {
                "row_id": "q2_for_task1",
                "task_row_id": "task_row_1",
                "question_text": "Another question for task 1",
                "answer_options": ["X", "Y", "Z"],
                "correct_answer": 2,
            },
            {
                "row_id": "q1_for_task2",
                "task_row_id": "task_row_2",
                "question_text": "Question for task 2",
                "answer_options": ["Yes", "No"],
                "correct_answer": 1,
            },
        ]
        mock_sheets_service.read_assessment_questions.return_value = []

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
        assert stats["questions_created"] == 3
        assert stats["errors"] == 0

        # Verify questions are assigned to correct tasks
        task1_questions = db_session.query(Question).filter(Question.task_id == "task_row_1").all()
        assert len(task1_questions) == 2

        task2_questions = db_session.query(Question).filter(Question.task_id == "task_row_2").all()
        assert len(task2_questions) == 1
        assert task2_questions[0].question_text == "Question for task 2"

    def test_sync_questions_mixed_create_and_update(self, db_session):
        """Test sync with mix of new and existing questions."""
        # Create task and existing question
        task = self._create_task(db_session)
        existing_question = Question(
            sheets_row_id="existing_question",
            task_id=task.sheets_row_id,
            question_text="Original text",
            answer_options=["Old A", "Old B"],
            correct_answer=0,
        )
        db_session.add(existing_question)
        db_session.commit()

        # Mock Google Sheets with one existing (to update) and one new question
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = [
            {
                "row_id": task.sheets_row_id,
                "level": "B1",
                "type": "text",
                "title": "Test Task",
                "content_text": "Task content for learning",
                "language_domain": "grammar",
                "status": "published",
            },
        ]
        mock_sheets_service.read_questions.return_value = [
            {
                "row_id": "existing_question",
                "task_row_id": task.sheets_row_id,
                "question_text": "Updated text",
                "answer_options": ["New A", "New B", "New C"],
                "correct_answer": 2,
            },
            {
                "row_id": "new_question",
                "task_row_id": task.sheets_row_id,
                "question_text": "Brand new question",
                "answer_options": ["Fresh A", "Fresh B"],
                "correct_answer": 1,
            },
        ]
        mock_sheets_service.read_assessment_questions.return_value = []

        mock_drive_service = MagicMock()

        service = ContentSyncService(
            sheets_service=mock_sheets_service,
            drive_service=mock_drive_service,
        )

        stats = service.sync_all(db=db_session)

        # One created, one updated
        assert stats["questions_created"] == 1
        assert stats["questions_updated"] == 1
        assert stats["errors"] == 0

        # Verify both questions in database
        questions = db_session.query(Question).all()
        assert len(questions) == 2

        updated_q = (
            db_session.query(Question).filter(Question.sheets_row_id == "existing_question").first()
        )
        assert updated_q.question_text == "Updated text"
        assert updated_q.correct_answer == 2

        new_q = db_session.query(Question).filter(Question.sheets_row_id == "new_question").first()
        assert new_q is not None
        assert new_q.question_text == "Brand new question"

    def test_sync_questions_handles_errors_gracefully(self, db_session):
        """Test that sync handles errors when reading questions from Google Sheets."""
        # Mock Google Sheets service to raise error on read_questions
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = []
        mock_sheets_service.read_questions.side_effect = ContentManagementError(
            "Failed to read questions from Google Sheets"
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

    def test_sync_questions_missing_row_id_skipped(self, db_session):
        """Test that questions without row_id are skipped."""
        task = self._create_task(db_session)

        # Mock Google Sheets service with question missing row_id
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = [
            {
                "row_id": task.sheets_row_id,
                "level": "B1",
                "type": "text",
                "title": "Test Task",
                "content_text": "Task content for learning",
                "language_domain": "grammar",
                "status": "published",
            },
        ]
        mock_sheets_service.read_questions.return_value = [
            {
                # No row_id field
                "task_row_id": task.sheets_row_id,
                "question_text": "Question without row_id",
                "answer_options": ["A", "B"],
                "correct_answer": 0,
            },
            {
                "row_id": "valid_question",
                "task_row_id": task.sheets_row_id,
                "question_text": "Valid question",
                "answer_options": ["X", "Y"],
                "correct_answer": 1,
            },
        ]
        mock_sheets_service.read_assessment_questions.return_value = []

        mock_drive_service = MagicMock()

        service = ContentSyncService(
            sheets_service=mock_sheets_service,
            drive_service=mock_drive_service,
        )

        stats = service.sync_all(db=db_session)

        # Only the valid question should be created
        assert stats["questions_created"] == 1

        questions = db_session.query(Question).all()
        assert len(questions) == 1
        assert questions[0].sheets_row_id == "valid_question"
