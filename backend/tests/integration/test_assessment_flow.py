"""Integration tests for assessment flow.

Tests the complete assessment flow: start → answer questions → receive level.
"""

import pytest

from src.english_tutor.models.user import User
from src.english_tutor.services.assessment import AssessmentService


class TestAssessmentFlow:
    """Test suite for complete assessment flow."""

    @pytest.mark.asyncio
    async def test_complete_assessment_flow(self, db_session):
        """Test complete assessment flow from start to level determination."""
        # Step 1: User starts conversation
        user = User(telegram_user_id="12345", is_active=True)
        db_session.add(user)
        db_session.commit()

        assert user.current_level is None

        # Step 2: Assessment initiated
        service = AssessmentService()
        # Provide question IDs for the assessment
        question_ids = ["q1", "q2", "q3"]
        assessment = await service.start_assessment(user.id, db_session, question_ids=question_ids)

        assert assessment.status == "in_progress"
        assert assessment.user_id == user.id
        assert len(assessment.questions) > 0

        # Step 3: User answers questions
        questions = [
            {"id": "q1", "weight": 1.0, "correct_answer": 0},
            {"id": "q2", "weight": 1.0, "correct_answer": 1},
            {"id": "q3", "weight": 1.0, "correct_answer": 2},
        ]

        answers = {
            "q1": 0,  # correct
            "q2": 1,  # correct
            "q3": 1,  # incorrect
        }

        # Step 4: Calculate score and determine level
        score = service.calculate_score(questions, answers)
        level = service.determine_level(score)

        # Step 5: Complete assessment
        completed_assessment = await service.complete_assessment(
            assessment.id,
            answers,
            score,
            level,
            db_session,
        )

        assert completed_assessment.status == "completed"
        assert completed_assessment.completed_at is not None
        assert completed_assessment.resulting_level == level
        assert completed_assessment.score == score

        # Step 6: Update user level
        user.current_level = level
        db_session.commit()

        assert user.current_level == level

    @pytest.mark.asyncio
    async def test_assessment_with_reassessment(self, db_session):
        """Test that user can retake assessment and update level."""
        # Initial assessment
        user = User(telegram_user_id="67890", is_active=True)
        db_session.add(user)
        db_session.commit()

        service = AssessmentService()
        assessment1 = await service.start_assessment(user.id, db_session, question_ids=["q1", "q2"])

        # Complete first assessment with lower score
        answers1 = {"q1": 0, "q2": 0}  # All correct for simplicity
        score1 = 0.35  # A2 level (0.20 <= score < 0.40)
        level1 = service.determine_level(score1)

        await service.complete_assessment(
            assessment1.id,
            answers1,
            score1,
            level1,
            db_session,
        )
        user.current_level = level1
        db_session.commit()

        assert user.current_level == "A2"

        # Reassessment with higher score
        assessment2 = await service.start_assessment(user.id, db_session, question_ids=["q1", "q2"])
        answers2 = {"q1": 0, "q2": 0}
        score2 = 0.7  # B2 level
        level2 = service.determine_level(score2)

        await service.complete_assessment(
            assessment2.id,
            answers2,
            score2,
            level2,
            db_session,
        )
        user.current_level = level2
        db_session.commit()

        assert user.current_level == "B2"
        assert user.current_level != level1

    @pytest.mark.asyncio
    async def test_assessment_abandoned_flow(self, db_session):
        """Test that abandoned assessments don't update user level."""
        user = User(telegram_user_id="99999", is_active=True)
        db_session.add(user)
        db_session.commit()

        service = AssessmentService()
        assessment = await service.start_assessment(user.id, db_session, question_ids=["q1", "q2"])

        # Abandon assessment
        await service.abandon_assessment(assessment.id, db_session)

        db_session.refresh(assessment)
        assert assessment.status == "abandoned"
        assert assessment.completed_at is None
        assert user.current_level is None
