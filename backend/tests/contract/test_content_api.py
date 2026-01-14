"""Contract tests for content management API.

Tests API endpoints match OpenAPI specification.
"""

import pytest
from fastapi.testclient import TestClient

from src.english_tutor.api.app import app
from src.english_tutor.api.dependencies import get_db
from src.english_tutor.models.task import Task


@pytest.fixture
def client(db_session):
    """Create test client with database dependency override."""
    # Ensure tables are created (they should be from conftest, but double-check)
    from src.english_tutor.models.base import Base

    engine = db_session.bind
    if engine:
        Base.metadata.create_all(engine)

    # Override get_db dependency to use test session
    def override_get_db():
        try:
            yield db_session
        finally:
            # Don't close the session here, let conftest handle it
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def existing_task_id(db_session) -> str:
    """Create a real task so by-id endpoints don't 404."""
    task = Task(
        level="B1",
        type="text",
        title="Contract Test Task",
        content_text="Contract test content",
        status="draft",
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return str(task.id)


class TestContentAPI:
    """Test suite for content management API endpoints."""

    def test_get_tasks_endpoint_exists(self, client):
        """Test that GET /tasks endpoint exists."""
        response = client.get("/tasks")
        # Should not return 404 (endpoint exists)
        assert response.status_code != 404

    def test_create_task_endpoint_exists(self, client):
        """Test that POST /tasks endpoint exists."""
        response = client.post("/tasks", json={})
        # Should not return 404 (endpoint exists)
        assert response.status_code != 404

    def test_get_task_by_id_endpoint_exists(self, client, existing_task_id):
        """Test that GET /tasks/{task_id} endpoint exists."""
        response = client.get(f"/tasks/{existing_task_id}")
        # Should not return 404 (endpoint exists)
        assert response.status_code != 404

    def test_update_task_endpoint_exists(self, client, existing_task_id):
        """Test that PUT /tasks/{task_id} endpoint exists."""
        response = client.put(f"/tasks/{existing_task_id}", json={})
        # Should not return 404 (endpoint exists)
        assert response.status_code != 404

    def test_delete_task_endpoint_exists(self, client, existing_task_id):
        """Test that DELETE /tasks/{task_id} endpoint exists."""
        response = client.delete(f"/tasks/{existing_task_id}")
        # Should not return 404 (endpoint exists)
        assert response.status_code != 404

    def test_get_questions_endpoint_exists(self, client, existing_task_id):
        """Test that GET /tasks/{task_id}/questions endpoint exists."""
        response = client.get(f"/tasks/{existing_task_id}/questions")
        # Should not return 404 (endpoint exists)
        assert response.status_code != 404

    def test_create_question_endpoint_exists(self, client):
        """Test that POST /tasks/{task_id}/questions endpoint exists."""
        response = client.post("/tasks/00000000-0000-0000-0000-000000000000/questions", json={})
        # Should not return 404 (endpoint exists)
        assert response.status_code != 404

    def test_publish_task_endpoint_exists(self, client, existing_task_id):
        """Test that POST /tasks/{task_id}/publish endpoint exists."""
        response = client.post(f"/tasks/{existing_task_id}/publish")
        # Should not return 404 (endpoint exists)
        assert response.status_code != 404
