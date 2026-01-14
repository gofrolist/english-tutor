"""Integration tests for content management flow.

Tests the complete content management flow: create task → add questions → publish.
"""

import pytest
from fastapi.testclient import TestClient

from src.english_tutor.api.app import app
from src.english_tutor.api.dependencies import get_db


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
        task_id = created_task["id"]

        assert created_task["level"] == "B1"
        assert created_task["type"] == "text"
        assert created_task["title"] == "Grammar: Past Simple"
        assert created_task["status"] == "draft"

        # Step 2: Add questions to the task
        question1_data = {
            "question_text": "What is the past tense of 'go'?",
            "answer_options": ["goed", "went", "gone", "going"],
            "correct_answer": 1,
            "weight": 1.0,
            "order": 1,
        }

        response = client.post(f"/tasks/{task_id}/questions", json=question1_data)
        assert response.status_code == 201
        created_question1 = response.json()

        assert created_question1["question_text"] == "What is the past tense of 'go'?"
        assert created_question1["correct_answer"] == 1
        assert created_question1["order"] == 1

        question2_data = {
            "question_text": "What is the past tense of 'eat'?",
            "answer_options": ["eated", "ate", "eaten", "eating"],
            "correct_answer": 1,
            "weight": 1.0,
            "order": 2,
        }

        response = client.post(f"/tasks/{task_id}/questions", json=question2_data)
        assert response.status_code == 201
        created_question2 = response.json()

        assert created_question2["question_text"] == "What is the past tense of 'eat'?"
        assert created_question2["order"] == 2

        # Step 3: Verify questions are listed for the task
        response = client.get(f"/tasks/{task_id}/questions")
        assert response.status_code == 200
        questions = response.json()

        assert len(questions) == 2
        question_ids = [q["id"] for q in questions]
        assert created_question1["id"] in question_ids
        assert created_question2["id"] in question_ids

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
        assert retrieved_task["id"] == task_id

    def test_create_task_with_audio_content(self, client, db_session):
        """Test creating a task with audio content."""
        task_data = {
            "level": "A2",
            "type": "audio",
            "title": "Listening: Daily Routine",
            "content_audio_url": "https://example.com/audio.mp3",
            "status": "draft",
        }

        response = client.post("/tasks", json=task_data)
        assert response.status_code == 201
        created_task = response.json()

        assert created_task["type"] == "audio"
        assert created_task["content_audio_url"] == "https://example.com/audio.mp3"
        assert created_task["content_text"] is None

    def test_create_task_with_video_content(self, client, db_session):
        """Test creating a task with video content."""
        task_data = {
            "level": "C1",
            "type": "video",
            "title": "Video: Academic Presentation",
            "content_video_url": "https://example.com/video.mp4",
            "status": "draft",
        }

        response = client.post("/tasks", json=task_data)
        assert response.status_code == 201
        created_task = response.json()

        assert created_task["type"] == "video"
        assert created_task["content_video_url"] == "https://example.com/video.mp4"
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
        task_id = response.json()["id"]

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
            "content_audio_url": "https://example.com/audio.mp3",
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
