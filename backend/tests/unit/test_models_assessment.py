"""Unit tests for Assessment model.

Tests for Assessment model creation, validation, and state transitions.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from src.english_tutor.models.assessment import Assessment
from src.english_tutor.models.user import User


class TestAssessmentModel:
    """Test suite for Assessment model."""

    def test_assessment_creation_with_required_fields(self, db_session):
        """Test creating an assessment with required fields."""
        user = User(telegram_user_id="11111", is_active=True)
        db_session.add(user)
        db_session.commit()

        assessment = Assessment(
            user_id=user.id,
            questions=["q1", "q2", "q3"],
            answers={},
            score=0.0,
            status="in_progress",
        )
        db_session.add(assessment)
        db_session.commit()

        assert assessment.id is not None
        assert assessment.user_id == user.id
        assert assessment.questions == ["q1", "q2", "q3"]
        assert assessment.answers == {}
        assert assessment.score == 0.0
        assert assessment.status == "in_progress"
        assert assessment.started_at is not None
        assert assessment.completed_at is None
        assert assessment.resulting_level is None

    def test_assessment_initial_status(self, db_session):
        """Test that new assessment has status 'in_progress'."""
        user = User(telegram_user_id="22222", is_active=True)
        db_session.add(user)
        db_session.commit()

        assessment = Assessment(
            user_id=user.id,
            questions=[],
            answers={},
            score=0.0,
        )
        db_session.add(assessment)
        db_session.commit()

        assert assessment.status == "in_progress"

    def test_assessment_completion(self, db_session):
        """Test completing an assessment."""
        user = User(telegram_user_id="33333", is_active=True)
        db_session.add(user)
        db_session.commit()

        assessment = Assessment(
            user_id=user.id,
            questions=["q1", "q2"],
            answers={"q1": 0, "q2": 1},
            score=0.75,  # Use normalized score (0.0-1.0)
            status="in_progress",
        )
        db_session.add(assessment)
        db_session.commit()

        assessment.status = "completed"
        assessment.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        assessment.resulting_level = "B1"
        db_session.commit()

        assert assessment.status == "completed"
        assert assessment.completed_at is not None
        assert assessment.resulting_level == "B1"

    def test_assessment_score_non_negative(self, db_session):
        """Test that assessment score must be non-negative."""
        user = User(telegram_user_id="44444", is_active=True)
        db_session.add(user)
        db_session.commit()

        assessment = Assessment(
            user_id=user.id,
            questions=[],
            answers={},
            score=-10.0,
            status="in_progress",
        )
        db_session.add(assessment)

        # This should raise a validation error or database constraint
        # Implementation will need to handle this validation
        with pytest.raises((ValueError, IntegrityError)):
            db_session.commit()

    def test_assessment_resulting_level_validation(self, db_session):
        """Test that resulting_level must be valid CEFR level."""
        user = User(telegram_user_id="55555", is_active=True)
        db_session.add(user)
        db_session.commit()

        valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]

        for level in valid_levels:
            assessment = Assessment(
                user_id=user.id,
                questions=[],
                answers={},
                score=0.5,  # Use normalized score (0.0-1.0)
                status="completed",
                resulting_level=level,
                completed_at=datetime.now(timezone.utc).replace(
                    tzinfo=None
                ),  # Required when status is completed
            )
            db_session.add(assessment)
            db_session.commit()
            assert assessment.resulting_level == level
            db_session.delete(assessment)
            db_session.commit()

    def test_assessment_abandoned_status(self, db_session):
        """Test setting assessment status to abandoned."""
        user = User(telegram_user_id="66666", is_active=True)
        db_session.add(user)
        db_session.commit()

        assessment = Assessment(
            user_id=user.id,
            questions=["q1"],
            answers={},
            score=0.0,
            status="in_progress",
        )
        db_session.add(assessment)
        db_session.commit()

        assessment.status = "abandoned"
        db_session.commit()

        assert assessment.status == "abandoned"
        assert assessment.completed_at is None
