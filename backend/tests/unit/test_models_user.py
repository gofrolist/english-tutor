"""Unit tests for User model.

Tests for User model creation, validation, and state transitions.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from src.english_tutor.models.user import User


class TestUserModel:
    """Test suite for User model."""

    def test_user_creation_with_required_fields(self, db_session):
        """Test creating a user with required fields."""
        user = User(
            telegram_user_id="12345",
            username="testuser",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        assert user.id is not None
        assert user.telegram_user_id == "12345"
        assert user.username == "testuser"
        assert user.current_level is None
        assert user.is_active is True
        assert user.created_at is not None
        assert user.updated_at is not None

    def test_user_creation_without_username(self, db_session):
        """Test creating a user without username (optional field)."""
        user = User(
            telegram_user_id="67890",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        assert user.telegram_user_id == "67890"
        assert user.username is None

    def test_user_telegram_user_id_unique(self, db_session):
        """Test that telegram_user_id must be unique."""
        user1 = User(telegram_user_id="11111", is_active=True)
        db_session.add(user1)
        db_session.commit()

        user2 = User(telegram_user_id="11111", is_active=True)
        db_session.add(user2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_user_current_level_validation(self, db_session):
        """Test that current_level must be valid CEFR level or None."""
        valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2", None]

        for level in valid_levels:
            user = User(
                telegram_user_id=str(1000 + hash(str(level)) % 10000),
                current_level=level,
                is_active=True,
            )
            db_session.add(user)
            db_session.commit()
            assert user.current_level == level
            db_session.delete(user)
            db_session.commit()

    def test_user_initial_state(self, db_session):
        """Test that new user has current_level as NULL."""
        user = User(telegram_user_id="99999", is_active=True)
        db_session.add(user)
        db_session.commit()

        assert user.current_level is None

    def test_user_level_update_after_assessment(self, db_session):
        """Test that user level can be updated after assessment."""
        user = User(telegram_user_id="88888", is_active=True)
        db_session.add(user)
        db_session.commit()

        assert user.current_level is None

        user.current_level = "B1"
        db_session.commit()

        assert user.current_level == "B1"
