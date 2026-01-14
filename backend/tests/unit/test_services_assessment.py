"""Unit tests for assessment scoring algorithm.

Tests for assessment scoring service and level determination.
"""

import pytest

from src.english_tutor.services.assessment import AssessmentService
from src.english_tutor.utils.exceptions import AssessmentError


class TestAssessmentScoring:
    """Test suite for assessment scoring algorithm."""

    def test_calculate_score_with_weighted_answers(self):
        """Test calculating score from weighted correct answers."""
        questions = [
            {"id": "q1", "weight": 1.0, "correct_answer": 0},
            {"id": "q2", "weight": 2.0, "correct_answer": 1},
            {"id": "q3", "weight": 1.5, "correct_answer": 2},
        ]

        answers = {
            "q1": 0,  # correct
            "q2": 1,  # correct
            "q3": 1,  # incorrect
        }

        service = AssessmentService()
        score = service.calculate_score(questions, answers)

        # q1: 1.0 point, q2: 2.0 points, q3: 0 points
        # Total weight: 1.0 + 2.0 + 1.5 = 4.5
        # Earned: 1.0 + 2.0 + 0 = 3.0
        # Score: 3.0 / 4.5 = 66.67%
        expected_score = (1.0 + 2.0) / (1.0 + 2.0 + 1.5)
        assert abs(score - expected_score) < 0.01

    def test_determine_level_from_score(self):
        """Test determining English level from score."""
        service = AssessmentService()

        # Test level thresholds
        # Note: Boundaries are inclusive on lower bound, exclusive on upper bound
        # So 0.40 maps to B1 (not A2), and 0.20 maps to A2 (not A1)
        test_cases = [
            (0.0, "A1"),
            (0.15, "A1"),
            (0.20, "A2"),  # Boundary: 0.20 is start of A2 range
            (0.25, "A2"),
            (0.39, "A2"),
            (0.40, "B1"),  # Boundary: 0.40 is start of B1 range
            (0.50, "B1"),
            (0.60, "B2"),  # Boundary: 0.60 is start of B2 range
            (0.65, "B2"),
            (0.75, "B2"),
            (0.80, "C1"),  # Boundary: 0.80 is start of C1 range
            (0.85, "C1"),
            (0.90, "C1"),
            (0.95, "C2"),  # Boundary: 0.95 is start of C2 range
            (0.98, "C2"),
            (1.0, "C2"),
        ]

        for score, expected_level in test_cases:
            level = service.determine_level(score)
            assert level == expected_level, f"Score {score} should map to {expected_level}"

    def test_calculate_score_with_missing_answers(self):
        """Test calculating score when some answers are missing."""
        questions = [
            {"id": "q1", "weight": 1.0, "correct_answer": 0},
            {"id": "q2", "weight": 1.0, "correct_answer": 1},
        ]

        answers = {
            "q1": 0,  # correct, q2 missing
        }

        service = AssessmentService()
        score = service.calculate_score(questions, answers)

        # Only q1 answered correctly: 1.0 / 2.0 = 0.5
        assert abs(score - 0.5) < 0.01

    def test_calculate_score_all_correct(self):
        """Test calculating score when all answers are correct."""
        questions = [
            {"id": "q1", "weight": 1.0, "correct_answer": 0},
            {"id": "q2", "weight": 1.0, "correct_answer": 1},
        ]

        answers = {
            "q1": 0,
            "q2": 1,
        }

        service = AssessmentService()
        score = service.calculate_score(questions, answers)

        assert abs(score - 1.0) < 0.01

    def test_calculate_score_all_incorrect(self):
        """Test calculating score when all answers are incorrect."""
        questions = [
            {"id": "q1", "weight": 1.0, "correct_answer": 0},
            {"id": "q2", "weight": 1.0, "correct_answer": 1},
        ]

        answers = {
            "q1": 1,  # incorrect
            "q2": 0,  # incorrect
        }

        service = AssessmentService()
        score = service.calculate_score(questions, answers)

        assert abs(score - 0.0) < 0.01

    def test_determine_level_invalid_score(self):
        """Test that invalid scores raise errors."""
        service = AssessmentService()

        with pytest.raises(AssessmentError):
            service.determine_level(-0.1)

        with pytest.raises(AssessmentError):
            service.determine_level(1.1)
