"""Deep evaluation engine tests."""

from __future__ import annotations

from generation.evaluation import evaluate_answer


def test_exact_correct() -> None:
    result = evaluate_answer(
        user_answer="2 and 3",
        correct_answer="2 and 3",
        concept="eigenvalues",
        difficulty_level="intermediate",
        user_id="test",
        topic="math",
        update_memory=False,
    )
    assert result["is_correct"] is True
    assert result["score"] >= 0.7
    assert result["error_type"] == "none"


def test_misinterpretation() -> None:
    result = evaluate_answer(
        user_answer="the determinant is -2",
        correct_answer="2 and 3",
        concept="eigenvalues",
        difficulty_level="intermediate",
        user_id="test",
        topic="math",
        update_memory=False,
    )
    assert result["is_correct"] is False
    assert result["error_type"] == "misinterpretation"


def test_conceptual_error_partial_credit() -> None:
    result = evaluate_answer(
        user_answer="entropy decreases in an isolated system",
        correct_answer="increase",
        concept="entropy",
        difficulty_level="intermediate",
        user_id="test",
        topic="physics",
        update_memory=False,
    )
    assert result["is_correct"] is False
    assert result["error_type"] == "conceptual_error"
    assert result["score"] > 0
