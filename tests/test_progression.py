"""Each progression action and the rule priorities."""

import pytest

from ale.engine.progression import StepInput, decide


def step(**kw):
    base = dict(concept="dot_product", difficulty=2, confidence=0.65, error_type="none", passed=True,
                consecutive_failures=0, next_concept="matrix_multiplication")
    base.update(kw)
    return decide(StepInput(**base))


def test_advance_when_confident():
    d = step(confidence=0.85)
    assert d.action == "advance" and d.next_concept == "matrix_multiplication"
    assert d.difficulty == 1 and d.lesson_level == "standard" and not d.reteach


def test_advance_on_last_concept_completes_topic():
    d = step(confidence=0.9, next_concept=None)
    assert d.action == "advance" and d.topic_complete and d.next_concept == "dot_product"


def test_practice_harder_in_the_middle_band_caps_at_max_difficulty():
    d = step(confidence=0.65, difficulty=1)
    assert d.action == "practice_harder" and d.difficulty == 2 and d.next_concept == "dot_product"
    assert step(confidence=0.65, difficulty=3).difficulty == 3


def test_repeat_when_confidence_low():
    d = step(confidence=0.3, passed=True)
    assert d.action == "repeat" and d.difficulty == 2 and not d.reteach


@pytest.mark.parametrize("conf,action", [(0.8, "advance"), (0.7999, "practice_harder"), (0.5, "practice_harder"), (0.4999, "repeat")])
def test_threshold_boundaries(conf, action):
    assert step(confidence=conf).action == action


@pytest.mark.parametrize("error", ["conceptual_error", "misinterpretation"])
def test_conceptual_and_misinterpretation_reteach_at_easier_level(error):
    d = step(error_type=error, passed=False, confidence=0.9, difficulty=3)
    assert d.action == "reteach" and d.reteach
    assert d.difficulty == 2 and d.lesson_level == "easy" and d.next_concept == "dot_product"
    assert step(error_type=error, passed=False, difficulty=1).difficulty == 1  # floor


def test_calculation_error_means_more_practice_not_reteach():
    d = step(error_type="calculation_error", passed=False, confidence=0.9)
    assert d.action == "repeat" and not d.reteach and d.lesson_level == "standard" and d.difficulty == 2
    assert d.rule == "calculation_error"


def test_three_consecutive_failures_reteach_even_for_slips():
    assert step(error_type="calculation_error", passed=False, consecutive_failures=2).action == "repeat"
    d = step(error_type="calculation_error", passed=False, consecutive_failures=3)
    assert d.action == "reteach" and d.rule == "failure_streak" and d.lesson_level == "easy"
    assert step(error_type="incomplete", passed=False, consecutive_failures=4).action == "reteach"


def test_failed_attempt_never_advances_or_raises_difficulty():
    d = step(error_type="incomplete", passed=False, confidence=0.95)
    assert d.action == "repeat" and d.difficulty == 2
    assert step(error_type="incomplete", passed=False, confidence=0.6).action == "repeat"


def test_every_decision_is_one_of_four_actions():
    seen = set()
    for conf in (0.1, 0.6, 0.9):
        for err, passed in (("none", True), ("incomplete", False), ("calculation_error", False), ("conceptual_error", False)):
            seen.add(step(confidence=conf, error_type=err, passed=passed).action)
    assert seen == {"advance", "practice_harder", "repeat", "reteach"}
