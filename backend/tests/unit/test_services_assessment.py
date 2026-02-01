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


class TestDetermineLevelFromQuestions:
    """Test suite for determine_level_from_questions (level-aware scoring)."""

    def test_assigns_a1_when_user_masters_only_a1(self):
        """User gets 88% on A1, 44% on A2 → should get A1 level."""
        service = AssessmentService()
        questions = [
            # A1 questions (9 total)
            {"id": "q1", "level": "A1", "correct_answer": 0},
            {"id": "q2", "level": "A1", "correct_answer": 1},
            {"id": "q3", "level": "A1", "correct_answer": 0},
            {"id": "q4", "level": "A1", "correct_answer": 1},
            {"id": "q5", "level": "A1", "correct_answer": 0},
            {"id": "q6", "level": "A1", "correct_answer": 1},
            {"id": "q7", "level": "A1", "correct_answer": 0},
            {"id": "q8", "level": "A1", "correct_answer": 1},
            {"id": "q9", "level": "A1", "correct_answer": 0},
            # A2 questions (9 total)
            {"id": "q10", "level": "A2", "correct_answer": 0},
            {"id": "q11", "level": "A2", "correct_answer": 1},
            {"id": "q12", "level": "A2", "correct_answer": 0},
            {"id": "q13", "level": "A2", "correct_answer": 1},
            {"id": "q14", "level": "A2", "correct_answer": 0},
            {"id": "q15", "level": "A2", "correct_answer": 1},
            {"id": "q16", "level": "A2", "correct_answer": 0},
            {"id": "q17", "level": "A2", "correct_answer": 1},
            {"id": "q18", "level": "A2", "correct_answer": 0},
        ]

        # 8/9 correct on A1 (88.9%), 4/9 correct on A2 (44.4%)
        answers = {
            # A1: 8 correct, 1 wrong
            "q1": 0,
            "q2": 1,
            "q3": 0,
            "q4": 1,
            "q5": 0,
            "q6": 1,
            "q7": 0,
            "q8": 1,
            "q9": 1,  # wrong
            # A2: 4 correct, 5 wrong
            "q10": 0,
            "q11": 1,
            "q12": 1,  # wrong
            "q13": 1,
            "q14": 1,  # wrong
            "q15": 1,
            "q16": 1,  # wrong
            "q17": 0,  # wrong
            "q18": 1,  # wrong
        }

        score = service.calculate_score(questions, answers)
        level = service.determine_level_from_questions(questions, answers, score)

        assert level == "A1", "User should get A1 (mastered A1 but struggled with A2)"

    def test_assigns_a2_when_user_masters_a1_and_a2(self):
        """User gets 80% on A1 and 70% on A2 → should get A2 level."""
        service = AssessmentService()
        questions = [{"id": f"a1_{i}", "level": "A1", "correct_answer": 0} for i in range(10)] + [
            {"id": f"a2_{i}", "level": "A2", "correct_answer": 0} for i in range(10)
        ]

        # 8/10 on A1 (80%), 7/10 on A2 (70%)
        answers = {f"a1_{i}": 0 if i < 8 else 1 for i in range(10)}  # 8 correct
        answers.update({f"a2_{i}": 0 if i < 7 else 1 for i in range(10)})  # 7 correct

        score = service.calculate_score(questions, answers)
        level = service.determine_level_from_questions(questions, answers, score)

        assert level == "A2", "User should get A2 (mastered both A1 and A2)"

    def test_assigns_b1_when_user_masters_a1_a2_b1(self):
        """User masters A1, A2, B1 (all >= 50%) → should get B1."""
        service = AssessmentService()
        questions = (
            [{"id": f"a1_{i}", "level": "A1", "correct_answer": 0} for i in range(10)]
            + [{"id": f"a2_{i}", "level": "A2", "correct_answer": 0} for i in range(10)]
            + [{"id": f"b1_{i}", "level": "B1", "correct_answer": 0} for i in range(10)]
        )

        # 60% on each level (mastered)
        answers = {}
        for level_prefix in ["a1", "a2", "b1"]:
            answers.update({f"{level_prefix}_{i}": 0 if i < 6 else 1 for i in range(10)})

        score = service.calculate_score(questions, answers)
        level = service.determine_level_from_questions(questions, answers, score)

        assert level == "B1", "User should get B1 (highest mastered level)"

    def test_assigns_a1_when_barely_passing_a1(self):
        """User gets exactly 50% on A1, 40% on A2 → should get A1."""
        service = AssessmentService()
        questions = [{"id": f"a1_{i}", "level": "A1", "correct_answer": 0} for i in range(10)] + [
            {"id": f"a2_{i}", "level": "A2", "correct_answer": 0} for i in range(10)
        ]

        # Exactly 5/10 on A1 (50%), 4/10 on A2 (40%)
        answers = {f"a1_{i}": 0 if i < 5 else 1 for i in range(10)}
        answers.update({f"a2_{i}": 0 if i < 4 else 1 for i in range(10)})

        score = service.calculate_score(questions, answers)
        level = service.determine_level_from_questions(questions, answers, score)

        assert level == "A1", "User should get A1 (50% is mastery threshold)"

    def test_assigns_a1_when_failing_all_levels(self):
        """User fails A1 (< 50%) → should still get A1 (minimum level)."""
        service = AssessmentService()
        questions = [{"id": f"a1_{i}", "level": "A1", "correct_answer": 0} for i in range(10)]

        # Only 3/10 correct on A1 (30%)
        answers = {f"a1_{i}": 0 if i < 3 else 1 for i in range(10)}

        score = service.calculate_score(questions, answers)
        level = service.determine_level_from_questions(questions, answers, score)

        assert level == "A1", "User should get A1 (minimum level, even if struggling)"

    def test_assigns_c2_when_mastering_all_levels(self):
        """User masters all levels including C2 → should get C2."""
        service = AssessmentService()
        questions = []
        for level in LEVELS_ORDER:
            questions.extend(
                [{"id": f"{level}_{i}", "level": level, "correct_answer": 0} for i in range(5)]
            )

        # 100% on all levels
        answers = {}
        for level in LEVELS_ORDER:
            answers.update({f"{level}_{i}": 0 for i in range(5)})

        score = service.calculate_score(questions, answers)
        level = service.determine_level_from_questions(questions, answers, score)

        assert level == "C2", "User should get C2 (mastered all levels)"

    def test_stops_at_first_failed_level(self):
        """User masters A1, A2, fails B1 → should get A2 (last mastered)."""
        service = AssessmentService()
        questions = (
            [{"id": f"a1_{i}", "level": "A1", "correct_answer": 0} for i in range(10)]
            + [{"id": f"a2_{i}", "level": "A2", "correct_answer": 0} for i in range(10)]
            + [{"id": f"b1_{i}", "level": "B1", "correct_answer": 0} for i in range(10)]
        )

        # 80% A1, 70% A2, 30% B1
        answers = {f"a1_{i}": 0 if i < 8 else 1 for i in range(10)}
        answers.update({f"a2_{i}": 0 if i < 7 else 1 for i in range(10)})
        answers.update({f"b1_{i}": 0 if i < 3 else 1 for i in range(10)})

        score = service.calculate_score(questions, answers)
        level = service.determine_level_from_questions(questions, answers, score)

        assert level == "A2", "User should get A2 (last level before failure)"

    def test_handles_missing_level_field(self):
        """Questions without level field fall back to score-based determination."""
        service = AssessmentService()
        questions = [
            {"id": "q1", "correct_answer": 0},  # No level field
            {"id": "q2", "correct_answer": 1},
        ]

        answers = {"q1": 0, "q2": 1}  # 100% correct

        score = service.calculate_score(questions, answers)
        level = service.determine_level_from_questions(questions, answers, score)

        # Should fall back to score-based (100% → C2)
        assert level == "C2", "Should fall back to score-based determination"

    def test_handles_partial_level_data(self):
        """Some questions with levels, some without → uses available level data."""
        service = AssessmentService()
        questions = [
            {"id": "q1", "level": "A1", "correct_answer": 0},
            {"id": "q2", "level": "A1", "correct_answer": 0},
            {"id": "q3", "correct_answer": 0},  # No level
            {"id": "q4", "level": "A2", "correct_answer": 0},
            {"id": "q5", "level": "A2", "correct_answer": 0},
        ]

        # 100% on A1, 0% on A2
        answers = {"q1": 0, "q2": 0, "q3": 0, "q4": 1, "q5": 1}

        score = service.calculate_score(questions, answers)
        level = service.determine_level_from_questions(questions, answers, score)

        assert level == "A1", "Should use available level data (A1 mastered, A2 failed)"

    def test_regression_bug_early_stop_b2_assignment(self):
        """Regression test for the original bug: 18 questions, 66.7% → should be A1, not B2."""
        service = AssessmentService()

        # Simulate the exact scenario from the bug report
        questions = []
        for i in range(9):
            questions.append({"id": f"assess-{i:03d}", "level": "A1", "correct_answer": 0})
        for i in range(9, 18):
            questions.append({"id": f"assess-{i:03d}", "level": "A2", "correct_answer": 0})

        # 8/9 correct on A1 (88.9%), 4/9 correct on A2 (44.4%) = 12/18 total (66.7%)
        answers = {}
        for i in range(9):
            answers[f"assess-{i:03d}"] = 0 if i != 0 else 1  # 8/9 correct
        for i in range(9, 18):
            answers[f"assess-{i:03d}"] = 0 if i in [9, 10, 12, 14] else 1  # 4/9 correct

        score = service.calculate_score(questions, answers)
        assert abs(score - 0.6667) < 0.01, "Score should be ~66.7%"

        level = service.determine_level_from_questions(questions, answers, score)

        # Bug was: 66.7% falls in B2 range (60-80%), so old logic assigned B2
        # Fix: Level-aware logic sees A1 mastered (88.9%), A2 failed (44.4%), assigns A1
        assert level == "A1", "User with 88% on A1 and 44% on A2 should get A1, not B2"

    def test_handles_unanswered_questions(self):
        """Questions that weren't answered are ignored in level determination."""
        service = AssessmentService()
        questions = [{"id": f"a1_{i}", "level": "A1", "correct_answer": 0} for i in range(10)] + [
            {"id": f"a2_{i}", "level": "A2", "correct_answer": 0} for i in range(10)
        ]

        # Only answer A1 questions (80% correct), don't answer A2
        answers = {f"a1_{i}": 0 if i < 8 else 1 for i in range(10)}

        score = service.calculate_score(questions, answers)
        level = service.determine_level_from_questions(questions, answers, score)

        assert level == "A1", "Should only consider answered questions"
