"""Integration tests for content management flow.

Tests the complete content management flow: create task → add questions → publish.
Also includes integration tests for content sync with mocked Google APIs.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.english_tutor.api.app import app
from src.english_tutor.api.dependencies import get_db
from src.english_tutor.models.assessment_question import AssessmentQuestion
from src.english_tutor.models.question import Question
from src.english_tutor.models.task import Task, TaskStatus
from src.english_tutor.services.content_sync import ContentSyncService


@pytest.fixture
def client(db_session):
    """Create test client with database override."""
    # Ensure tables are created (they should be from conftest, but double-check)
    from src.english_tutor.models.base import Base

    engine = db_session.bind
    if engine:
        Base.metadata.create_all(engine)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


class TestContentManagementFlow:
    """Test suite for complete content management flow."""

    def test_complete_content_management_flow(self, client, db_session):
        """Test complete content management flow from task creation to publishing."""
        # Step 1: Create a new task
        task_data = {
            "level": "B1",
            "type": "text",
            "title": "Grammar: Past Simple",
            "content_text": "The past simple tense is used to describe completed actions in the past.",
            "explanation": "Use past simple for actions that happened at a specific time in the past.",
            "status": "draft",
        }

        response = client.post("/tasks", json=task_data)
        assert response.status_code == 201
        created_task = response.json()
        task_id = created_task["sheets_row_id"]

        assert created_task["level"] == "B1"
        assert created_task["type"] == "text"
        assert created_task["title"] == "Grammar: Past Simple"
        assert created_task["status"] == "draft"

        # Step 2: Add questions to the task
        question1_data = {
            "question_text": "What is the past tense of 'go'?",
            "answer_options": ["goed", "went", "gone", "going"],
            "correct_answer": 1,
        }

        response = client.post(f"/tasks/{task_id}/questions", json=question1_data)
        assert response.status_code == 201
        created_question1 = response.json()

        assert created_question1["question_text"] == "What is the past tense of 'go'?"
        assert created_question1["correct_answer"] == 1

        question2_data = {
            "question_text": "What is the past tense of 'eat'?",
            "answer_options": ["eated", "ate", "eaten", "eating"],
            "correct_answer": 1,
        }

        response = client.post(f"/tasks/{task_id}/questions", json=question2_data)
        assert response.status_code == 201
        created_question2 = response.json()

        assert created_question2["question_text"] == "What is the past tense of 'eat'?"

        # Step 3: Verify questions are listed for the task
        response = client.get(f"/tasks/{task_id}/questions")
        assert response.status_code == 200
        questions = response.json()

        assert len(questions) == 2
        question_ids = [q["sheets_row_id"] for q in questions]
        assert created_question1["sheets_row_id"] in question_ids
        assert created_question2["sheets_row_id"] in question_ids

        # Step 4: Publish the task
        response = client.post(f"/tasks/{task_id}/publish")
        assert response.status_code == 200
        published_task = response.json()

        assert published_task["status"] == "published"

        # Step 5: Verify task can be retrieved
        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        retrieved_task = response.json()

        assert retrieved_task["status"] == "published"
        assert retrieved_task["sheets_row_id"] == task_id

    def test_create_task_with_audio_content(self, client, db_session):
        """Test creating a task with audio content."""
        task_data = {
            "level": "A2",
            "type": "audio",
            "title": "Listening: Daily Routine",
            "content_url": "https://example.com/audio.mp3",
            "status": "draft",
        }

        response = client.post("/tasks", json=task_data)
        assert response.status_code == 201
        created_task = response.json()

        assert created_task["type"] == "audio"
        assert created_task["content_url"] == "https://example.com/audio.mp3"
        assert created_task["content_text"] is None

    def test_create_task_with_video_content(self, client, db_session):
        """Test creating a task with video content."""
        task_data = {
            "level": "C1",
            "type": "video",
            "title": "Video: Academic Presentation",
            "content_url": "https://example.com/video.mp4",
            "status": "draft",
        }

        response = client.post("/tasks", json=task_data)
        assert response.status_code == 201
        created_task = response.json()

        assert created_task["type"] == "video"
        assert created_task["content_url"] == "https://example.com/video.mp4"
        assert created_task["content_text"] is None

    def test_update_task_before_publishing(self, client, db_session):
        """Test updating a task before publishing."""
        # Create task
        task_data = {
            "level": "B1",
            "type": "text",
            "title": "Original Title",
            "content_text": "Original content",
            "status": "draft",
        }

        response = client.post("/tasks", json=task_data)
        assert response.status_code == 201
        task_id = response.json()["sheets_row_id"]

        # Update task
        update_data = {
            "title": "Updated Title",
            "content_text": "Updated content",
        }

        response = client.put(f"/tasks/{task_id}", json=update_data)
        assert response.status_code == 200
        updated_task = response.json()

        assert updated_task["title"] == "Updated Title"
        assert updated_task["content_text"] == "Updated content"
        assert updated_task["status"] == "draft"

    def test_task_filtering(self, client, db_session):
        """Test filtering tasks by level, type, and status."""
        # Create tasks with different properties
        task1_data = {
            "level": "B1",
            "type": "text",
            "title": "B1 Text Task",
            "content_text": "Content",
            "status": "published",
        }
        task2_data = {
            "level": "B1",
            "type": "audio",
            "title": "B1 Audio Task",
            "content_url": "https://example.com/audio.mp3",
            "status": "draft",
        }
        task3_data = {
            "level": "A2",
            "type": "text",
            "title": "A2 Text Task",
            "content_text": "Content",
            "status": "published",
        }

        client.post("/tasks", json=task1_data)
        client.post("/tasks", json=task2_data)
        client.post("/tasks", json=task3_data)

        # Filter by level
        response = client.get("/tasks?level=B1")
        assert response.status_code == 200
        tasks = response.json()
        assert all(task["level"] == "B1" for task in tasks)

        # Filter by type
        response = client.get("/tasks?task_type=text")
        assert response.status_code == 200
        tasks = response.json()
        assert all(task["type"] == "text" for task in tasks)

        # Filter by status
        response = client.get("/tasks?status=published")
        assert response.status_code == 200
        tasks = response.json()
        assert all(task["status"] == "published" for task in tasks)


class TestContentSyncFlow:
    """Integration tests for content sync flow with mocked Google APIs."""

    def test_complete_sync_flow_creates_tasks_questions_assessments(self, db_session):
        """Test complete content sync flow: sync tasks, then questions, then assessments."""
        # Mock Google Sheets service with complete dataset
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = [
            {
                "row_id": "task_sync_1",
                "level": "B1",
                "type": "text",
                "title": "Grammar: Past Tense",
                "content_text": "Learn about the past tense in English",
                "language_domain": "grammar",
                "explanation": "Past tense is used to describe completed actions",
                "status": "published",
            },
            {
                "row_id": "task_sync_2",
                "level": "A2",
                "type": "audio",
                "title": "Listening: Daily Routine",
                "content_audio_drive_id": "drive_audio_123",
                "language_domain": "listening",
                "status": "published",
            },
        ]
        mock_sheets_service.read_questions.return_value = [
            {
                "row_id": "question_sync_1",
                "task_row_id": "task_sync_1",
                "question_text": "What is the past tense of 'go'?",
                "answer_options": ["goed", "went", "gone", "going"],
                "correct_answer": 1,
            },
            {
                "row_id": "question_sync_2",
                "task_row_id": "task_sync_1",
                "question_text": "What is the past tense of 'eat'?",
                "answer_options": ["eated", "ate", "eaten", "eating"],
                "correct_answer": 1,
            },
        ]
        mock_sheets_service.read_assessment_questions.return_value = [
            {
                "row_id": "assess_sync_1",
                "level": "B1",
                "question_text": "What is the past tense of 'see'?",
                "answer_options": ["seed", "saw", "seen", "seeing"],
                "correct_answer": 1,
            },
        ]

        # Mock Google Drive service
        mock_drive_service = MagicMock()
        mock_drive_service.get_file_download_url.return_value = (
            "https://drive.google.com/audio/drive_audio_123"
        )

        # Create sync service with mocks
        service = ContentSyncService(
            sheets_service=mock_sheets_service,
            drive_service=mock_drive_service,
        )

        # Run full sync
        stats = service.sync_all(db=db_session)

        # Verify stats
        assert stats["tasks_created"] == 2
        assert stats["questions_created"] == 2
        assert stats["assessment_questions_created"] == 1
        assert stats["errors"] == 0

        # Verify tasks were created
        tasks = db_session.query(Task).all()
        assert len(tasks) == 2

        task1 = db_session.query(Task).filter(Task.sheets_row_id == "task_sync_1").first()
        assert task1 is not None
        assert task1.level == "B1"
        assert task1.type == "text"
        assert task1.title == "Grammar: Past Tense"
        assert task1.status == TaskStatus.PUBLISHED

        task2 = db_session.query(Task).filter(Task.sheets_row_id == "task_sync_2").first()
        assert task2 is not None
        assert task2.type == "audio"
        assert task2.content_url == "https://drive.google.com/audio/drive_audio_123"

        # Verify questions were created and linked to tasks
        questions = db_session.query(Question).all()
        assert len(questions) == 2

        q1 = db_session.query(Question).filter(Question.sheets_row_id == "question_sync_1").first()
        assert q1 is not None
        assert q1.task_id == "task_sync_1"
        assert q1.question_text == "What is the past tense of 'go'?"

        # Verify assessment questions were created
        assessments = db_session.query(AssessmentQuestion).all()
        assert len(assessments) == 1
        assert assessments[0].level == "B1"

    def test_sync_flow_updates_existing_content(self, db_session):
        """Test sync flow updates existing tasks and questions when data changes."""
        # Create existing task and question
        existing_task = Task(
            sheets_row_id="task_update_1",
            level="B1",
            type="text",
            title="Original Title",
            content_text="Original content",
            status=TaskStatus.DRAFT,
        )
        db_session.add(existing_task)
        db_session.commit()

        existing_question = Question(
            sheets_row_id="question_update_1",
            task_id="task_update_1",
            question_text="Original question?",
            answer_options=["a", "b", "c", "d"],
            correct_answer=0,
        )
        db_session.add(existing_question)
        db_session.commit()

        # Mock Google Sheets service with updated data
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = [
            {
                "row_id": "task_update_1",
                "level": "B1",
                "type": "text",
                "title": "Updated Title",
                "content_text": "Updated content",
                "explanation": "New explanation",
                "status": "published",
            },
        ]
        mock_sheets_service.read_questions.return_value = [
            {
                "row_id": "question_update_1",
                "task_row_id": "task_update_1",
                "question_text": "Updated question?",
                "answer_options": ["x", "y", "z", "w"],
                "correct_answer": 2,
            },
        ]
        mock_sheets_service.read_assessment_questions.return_value = []

        mock_drive_service = MagicMock()

        service = ContentSyncService(
            sheets_service=mock_sheets_service,
            drive_service=mock_drive_service,
        )

        stats = service.sync_all(db=db_session)

        # Verify updates
        assert stats["tasks_created"] == 0
        assert stats["tasks_updated"] == 1
        assert stats["questions_created"] == 0
        assert stats["questions_updated"] == 1

        # Verify task was updated
        db_session.refresh(existing_task)
        assert existing_task.title == "Updated Title"
        assert existing_task.content_text == "Updated content"
        assert existing_task.status == TaskStatus.PUBLISHED

        # Verify question was updated
        db_session.refresh(existing_question)
        assert existing_question.question_text == "Updated question?"
        assert existing_question.correct_answer == 2

    def test_sync_flow_handles_questions_for_nonexistent_tasks(self, db_session):
        """Test sync handles questions referencing tasks that don't exist yet."""
        # Mock sheets service with questions for a task that will be created
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = [
            {
                "row_id": "new_task_sync",
                "level": "A2",
                "type": "text",
                "title": "New Task",
                "content_text": "New content",
                "status": "published",
            },
        ]
        mock_sheets_service.read_questions.return_value = [
            {
                "row_id": "q_for_new_task",
                "task_row_id": "new_task_sync",
                "question_text": "Question for new task?",
                "answer_options": ["1", "2", "3", "4"],
                "correct_answer": 0,
            },
        ]
        mock_sheets_service.read_assessment_questions.return_value = []

        mock_drive_service = MagicMock()

        service = ContentSyncService(
            sheets_service=mock_sheets_service,
            drive_service=mock_drive_service,
        )

        stats = service.sync_all(db=db_session)

        # Both should be created since tasks are synced first
        assert stats["tasks_created"] == 1
        assert stats["questions_created"] == 1

        # Verify question is linked to task
        question = (
            db_session.query(Question).filter(Question.sheets_row_id == "q_for_new_task").first()
        )
        assert question is not None
        assert question.task_id == "new_task_sync"

    def test_sync_flow_with_audio_and_video_urls(self, db_session):
        """Test sync resolves Google Drive URLs for audio and video content."""
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = [
            {
                "row_id": "audio_sync_task",
                "level": "B1",
                "type": "audio",
                "title": "Audio Lesson",
                "content_audio_drive_id": "audio_drive_id_456",
                "status": "published",
            },
            {
                "row_id": "video_sync_task",
                "level": "C1",
                "type": "video",
                "title": "Video Lesson",
                "content_video_drive_id": "video_drive_id_789",
                "status": "published",
            },
        ]
        mock_sheets_service.read_questions.return_value = []
        mock_sheets_service.read_assessment_questions.return_value = []

        # Mock Drive service to return different URLs based on file ID
        mock_drive_service = MagicMock()

        def mock_get_url(file_id):
            return f"https://drive.google.com/file/{file_id}"

        mock_drive_service.get_file_download_url.side_effect = mock_get_url

        service = ContentSyncService(
            sheets_service=mock_sheets_service,
            drive_service=mock_drive_service,
        )

        stats = service.sync_all(db=db_session)

        assert stats["tasks_created"] == 2

        # Verify audio URL was resolved
        audio_task = db_session.query(Task).filter(Task.sheets_row_id == "audio_sync_task").first()
        assert audio_task.content_url == "https://drive.google.com/file/audio_drive_id_456"

        # Verify video URL was resolved
        video_task = db_session.query(Task).filter(Task.sheets_row_id == "video_sync_task").first()
        assert video_task.content_url == "https://drive.google.com/file/video_drive_id_789"

    def test_sync_flow_transaction_rollback_on_error(self, db_session):
        """Test that sync rolls back transaction on critical error."""
        # Create a task first to ensure rollback works
        existing_task = Task(
            sheets_row_id="task_before_error",
            level="B1",
            type="text",
            title="Task Before Error",
            content_text="Content",
            status=TaskStatus.PUBLISHED,
        )
        db_session.add(existing_task)
        db_session.commit()
        original_count = db_session.query(Task).count()

        # Mock sheets service to fail during read
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.side_effect = Exception("Connection failed")

        mock_drive_service = MagicMock()

        service = ContentSyncService(
            sheets_service=mock_sheets_service,
            drive_service=mock_drive_service,
        )

        # Sync should raise exception
        with pytest.raises(Exception) as exc_info:
            service.sync_all(db=db_session)

        assert "Connection failed" in str(exc_info.value)

        # Task count should remain unchanged (no partial commits)
        assert db_session.query(Task).count() == original_count

    def test_sync_flow_multiple_levels_and_types(self, db_session):
        """Test sync handles content across multiple levels and types correctly."""
        mock_sheets_service = MagicMock()
        mock_sheets_service.read_tasks.return_value = [
            {
                "row_id": "t_a1_text",
                "level": "A1",
                "type": "text",
                "title": "A1 Text",
                "content_text": "A1 content",
                "status": "published",
            },
            {
                "row_id": "t_a2_audio",
                "level": "A2",
                "type": "audio",
                "title": "A2 Audio",
                "content_audio_drive_id": "a2_audio",
                "status": "published",
            },
            {
                "row_id": "t_b1_text",
                "level": "B1",
                "type": "text",
                "title": "B1 Text",
                "content_text": "B1 content",
                "status": "published",
            },
            {
                "row_id": "t_b2_video",
                "level": "B2",
                "type": "video",
                "title": "B2 Video",
                "content_video_drive_id": "b2_video",
                "status": "draft",
            },
            {
                "row_id": "t_c1_text",
                "level": "C1",
                "type": "text",
                "title": "C1 Text",
                "content_text": "C1 content",
                "status": "published",
            },
        ]
        mock_sheets_service.read_questions.return_value = [
            {
                "row_id": "q_a1_1",
                "task_row_id": "t_a1_text",
                "question_text": "A1 Q1?",
                "answer_options": ["a", "b"],
                "correct_answer": 0,
            },
            {
                "row_id": "q_b1_1",
                "task_row_id": "t_b1_text",
                "question_text": "B1 Q1?",
                "answer_options": ["a", "b", "c"],
                "correct_answer": 1,
            },
            {
                "row_id": "q_c1_1",
                "task_row_id": "t_c1_text",
                "question_text": "C1 Q1?",
                "answer_options": ["a", "b", "c", "d"],
                "correct_answer": 2,
            },
        ]
        mock_sheets_service.read_assessment_questions.return_value = [
            {
                "row_id": "assess_a1",
                "level": "A1",
                "question_text": "A1 Assessment?",
                "answer_options": ["yes", "no"],
                "correct_answer": 0,
            },
            {
                "row_id": "assess_b1",
                "level": "B1",
                "question_text": "B1 Assessment?",
                "answer_options": ["yes", "no"],
                "correct_answer": 1,
            },
            {
                "row_id": "assess_c1",
                "level": "C1",
                "question_text": "C1 Assessment?",
                "answer_options": ["yes", "no"],
                "correct_answer": 0,
            },
        ]

        mock_drive_service = MagicMock()
        mock_drive_service.get_file_download_url.side_effect = lambda fid: (
            f"https://drive.google.com/{fid}"
        )

        service = ContentSyncService(
            sheets_service=mock_sheets_service,
            drive_service=mock_drive_service,
        )

        stats = service.sync_all(db=db_session)

        assert stats["tasks_created"] == 5
        assert stats["questions_created"] == 3
        assert stats["assessment_questions_created"] == 3
        assert stats["errors"] == 0

        # Verify levels
        tasks = db_session.query(Task).all()
        levels = {t.level for t in tasks}
        assert levels == {"A1", "A2", "B1", "B2", "C1"}

        # Verify types
        types = {t.type for t in tasks}
        assert types == {"text", "audio", "video"}

        # Verify assessment levels
        assessments = db_session.query(AssessmentQuestion).all()
        assess_levels = {a.level for a in assessments}
        assert assess_levels == {"A1", "B1", "C1"}
