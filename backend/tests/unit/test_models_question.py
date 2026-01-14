"""Unit tests for Question model.

Tests for Question model creation, validation, and relationships.
"""

from src.english_tutor.models.question import Question
from src.english_tutor.models.task import Task


class TestQuestionModel:
    """Test suite for Question model."""

    def test_question_creation_with_required_fields(self, db_session):
        """Test creating a question with required fields."""
        task = Task(
            level="B1",
            type="text",
            title="Test Task",
            content_text="Test content",
            status="published",
        )
        db_session.add(task)
        db_session.commit()

        question = Question(
            task_id=task.id,
            question_text="What is the past tense of 'go'?",
            answer_options=["goed", "went", "gone", "going"],
            correct_answer=1,
            order=1,
        )
        db_session.add(question)
        db_session.commit()

        assert question.id is not None
        assert question.task_id == task.id
        assert question.question_text == "What is the past tense of 'go'?"
        assert question.answer_options == ["goed", "went", "gone", "going"]
        assert question.correct_answer == 1
        assert question.order == 1
        assert question.weight == 1.0  # default weight
        assert question.created_at is not None
        assert question.updated_at is not None

    def test_question_weight_custom(self, db_session):
        """Test creating a question with custom weight."""
        task = Task(
            level="B1",
            type="text",
            title="Test Task",
            content_text="Test content",
            status="published",
        )
        db_session.add(task)
        db_session.commit()

        question = Question(
            task_id=task.id,
            question_text="Important question",
            answer_options=["A", "B"],
            correct_answer=0,
            order=1,
            weight=2.5,
        )
        db_session.add(question)
        db_session.commit()

        assert question.weight == 2.5

    def test_question_correct_answer_validation(self, db_session):
        """Test that correct_answer must be valid index."""
        task = Task(
            level="B1",
            type="text",
            title="Test Task",
            content_text="Test content",
            status="published",
        )
        db_session.add(task)
        db_session.commit()

        answer_options = ["A", "B", "C"]

        # Valid indices
        for correct_idx in range(len(answer_options)):
            question = Question(
                task_id=task.id,
                question_text=f"Question {correct_idx}",
                answer_options=answer_options,
                correct_answer=correct_idx,
                order=correct_idx + 1,
            )
            db_session.add(question)
            db_session.commit()
            assert question.correct_answer == correct_idx
            db_session.delete(question)
            db_session.commit()

    def test_question_order(self, db_session):
        """Test that questions can have different order values."""
        task = Task(
            level="B1",
            type="text",
            title="Test Task",
            content_text="Test content",
            status="published",
        )
        db_session.add(task)
        db_session.commit()

        question1 = Question(
            task_id=task.id,
            question_text="First question",
            answer_options=["A", "B"],
            correct_answer=0,
            order=1,
        )
        question2 = Question(
            task_id=task.id,
            question_text="Second question",
            answer_options=["A", "B"],
            correct_answer=0,
            order=2,
        )

        db_session.add(question1)
        db_session.add(question2)
        db_session.commit()

        assert question1.order == 1
        assert question2.order == 2

    def test_question_relationship_to_task(self, db_session):
        """Test that question belongs to a task."""
        task = Task(
            level="B1",
            type="text",
            title="Test Task",
            content_text="Test content",
            status="published",
        )
        db_session.add(task)
        db_session.commit()

        question = Question(
            task_id=task.id,
            question_text="Test question",
            answer_options=["A", "B"],
            correct_answer=0,
            order=1,
        )
        db_session.add(question)
        db_session.commit()

        assert question.task_id == task.id
        assert question in task.questions
