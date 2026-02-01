"""Unit tests for assessment scoring algorithm.

Tests for assessment scoring service, level determination, question selection,
and early-stop (struggling) logic.
"""

import pytest

from src.english_tutor.models.assessment_question import AssessmentQuestion
from src.english_tutor.services.assessment import (
    LEVELS_ORDER,
    AssessmentService,
)
from src.english_tutor.utils.exceptions import AssessmentError


class TestAssessmentScoring:
    """Test suite for assessment scoring algorithm."""

    def test_calculate_score_from_correct_answers(self):
        """Test calculating score from correct answers (fraction correct)."""
        questions = [
            {"id": "q1", "correct_answer": 0},
            {"id": "q2", "correct_answer": 1},
            {"id": "q3", "correct_answer": 2},
        ]

        answers = {
            "q1": 0,  # correct
            "q2": 1,  # correct
            "q3": 1,  # incorrect
        }

        service = AssessmentService()
        score = service.calculate_score(questions, answers)

        # 2 correct out of 3 answered -> 2/3
        assert abs(score - 2.0 / 3.0) < 0.01

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
            {"id": "q1", "correct_answer": 0},
            {"id": "q2", "correct_answer": 1},
        ]

        answers = {
            "q1": 0,  # correct, q2 missing
        }

        service = AssessmentService()
        score = service.calculate_score(questions, answers)

        # Only q1 answered; 1 correct out of 1 answered -> 1.0
        assert abs(score - 1.0) < 0.01

    def test_calculate_score_all_correct(self):
        """Test calculating score when all answers are correct."""
        questions = [
            {"id": "q1", "correct_answer": 0},
            {"id": "q2", "correct_answer": 1},
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
            {"id": "q1", "correct_answer": 0},
            {"id": "q2", "correct_answer": 1},
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


class TestAssessmentQuestionSelection:
    """Test suite for _select_assessment_questions (all questions per level, no cap)."""

    def test_selects_all_questions_per_level_ordered(self, db_session):
        """Selection returns all questions per level, ordered by level then row_id."""
        # A1: 10 questions, A2: 5, B1: 3 (content can vary per level)
        counts = {"A1": 10, "A2": 5, "B1": 3, "B2": 0, "C1": 0, "C2": 0}
        for level in LEVELS_ORDER:
            for i in range(counts.get(level, 0)):
                q = AssessmentQuestion(
                    sheets_row_id=f"assess-{level}-{i:02d}",
                    level=level,
                    question_text=f"Q {level} {i}",
                    answer_options=["A", "B"],
                    correct_answer=0,
                )
                db_session.add(q)
        db_session.commit()

        service = AssessmentService()
        ids = service._select_assessment_questions(db_session)

        assert len(ids) == 18  # 10 + 5 + 3
        assert ids[0].startswith("assess-A1-")
        assert ids[9].startswith("assess-A1-")
        assert ids[10].startswith("assess-A2-")
        assert ids[14].startswith("assess-A2-")
        assert ids[15].startswith("assess-B1-")
        levels_in_order = [qid.split("-")[1] for qid in ids]
        assert levels_in_order == sorted(
            levels_in_order, key=lambda level_key: LEVELS_ORDER.index(level_key)
        )

    def test_selects_all_available_no_limit(self, db_session):
        """All questions from DB are returned; no total or per-level limit."""
        for level in ["A1", "A2"]:
            for i in range(5):
                q = AssessmentQuestion(
                    sheets_row_id=f"q-{level}-{i}",
                    level=level,
                    question_text="Q",
                    answer_options=["A", "B"],
                    correct_answer=0,
                )
                db_session.add(q)
        db_session.commit()

        service = AssessmentService()
        ids = service._select_assessment_questions(db_session)
        assert len(ids) == 10

    def test_selects_questions_from_start_from_level(self, db_session):
        """When start_from_level is set, questions from earlier levels are excluded."""
        for level in ["A1", "A2", "B1"]:
            for i in range(3):
                q = AssessmentQuestion(
                    sheets_row_id=f"q-{level}-{i}",
                    level=level,
                    question_text="Q",
                    answer_options=["A", "B"],
                    correct_answer=0,
                )
                db_session.add(q)
        db_session.commit()

        service = AssessmentService()
        ids = service._select_assessment_questions(db_session, start_from_level="A2")

        assert len(ids) == 6  # Only A2 (3) + B1 (3), no A1
        assert all("A1" not in qid for qid in ids)
        assert ids[0].startswith("q-A2-")
        assert ids[3].startswith("q-B1-")


class TestShouldOfferEarlyStop:
    """Test suite for should_offer_early_stop (struggling detection)."""

    def test_returns_false_when_few_answers(self):
        """Do not offer early stop before min_answered."""
        service = AssessmentService()
        questions = [{"id": f"q{i}", "correct_answer": 0} for i in range(20)]
        answers = {f"q{i}": 0 for i in range(10)}  # 10 correct
        assert service.should_offer_early_stop(questions, answers) is False

    def test_returns_true_when_last_four_wrong(self):
        """Offer early stop when last 4 answers are wrong (consecutive wrong)."""
        service = AssessmentService()
        questions = [{"id": f"q{i}", "correct_answer": 0} for i in range(20)]
        answers = {}
        for i in range(12):
            answers[f"q{i}"] = 0 if i < 8 else 1  # first 8 correct, last 4 wrong
        assert service.should_offer_early_stop(questions, answers) is True

    def test_returns_true_when_low_accuracy_in_last_window(self):
        """Offer early stop when in last 6 answers at most 2 are correct."""
        service = AssessmentService()
        questions = [{"id": f"q{i}", "correct_answer": 0} for i in range(20)]
        answers = {}
        for i in range(15):
            # Last 6: only 2 correct (q9, q10), rest wrong
            answers[f"q{i}"] = 0 if i in (9, 10) else 1
        assert service.should_offer_early_stop(questions, answers) is True

    def test_returns_false_when_doing_well(self):
        """Do not offer early stop when accuracy is good."""
        service = AssessmentService()
        questions = [{"id": f"q{i}", "correct_answer": 0} for i in range(20)]
        answers = {f"q{i}": 0 for i in range(15)}  # all correct
        assert service.should_offer_early_stop(questions, answers) is False

    def test_returns_false_when_recent_answers_good(self):
        """Do not offer when last window has enough correct (even if earlier was bad)."""
        service = AssessmentService()
        questions = [{"id": f"q{i}", "correct_answer": 0} for i in range(20)]
        answers = {}
        for i in range(14):
            answers[f"q{i}"] = 1 if i < 8 else 0  # first 8 wrong, last 6 correct
        assert service.should_offer_early_stop(questions, answers) is False
