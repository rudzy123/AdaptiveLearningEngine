"""Each of the five evaluation layers, plus integrity of the whole problem bank."""

import pytest

from ale.engine.curriculum import load_curriculum
from ale.engine.evaluation import (
    evaluate,
    layer_confidence,
    layer_exact,
    layer_partial,
    layer_reasoning,
    learning_signal,
    parse,
    parse_complexity,
    update_confidence,
)
from ale.engine.text import numbers

CUR = load_curriculum()


def P(pid):
    return CUR.problem(pid)


def ev(pid, answer, reasoning="", before=0.5, attempts=0):
    return evaluate(P(pid), answer, reasoning, confidence_before=before, attempts=attempts)


def layer(e, name):
    return next(layer for layer in e.layers if layer["name"] == name)


# ---- parsing ---------------------------------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("(4, 7)", [4, 7]),
        ("6, \u22123", [6, -3]),
        ("lambda1 = 2 and lambda2 = 3", [2, 3]),
        ("1,000,000", [1000000]),
        ("4/2", [2]),
        ("0.5", [0.5]),
        ("four", [4]),
        ("2\u00d74", [2, 4]),
    ],
)
def test_number_parsing(text, expected):
    assert numbers(text) == expected


@pytest.mark.parametrize(
    "text,forms",
    [
        ("O(n log n)", {"nlogn"}),
        ("O(n log(n))", {"nlogn"}),
        ("n*log(n)", {"nlogn"}),
        ("O(n^2)", {"n2"}),
        ("n squared", {"n2"}),
        ("quadratic", {"n2"}),
        ("O(n\u00b2) not O(n)", {"n2", "n"}),
        ("banana", set()),
    ],
)
def test_complexity_parsing(text, forms):
    assert parse_complexity(text) == forms


# ---- layer 1: exact / numeric match -----------------------------------------

@pytest.mark.parametrize(
    "pid,answer,ok",
    [
        ("vec-1", "4, 7", True),
        ("vec-1", "(4, 7)", True),
        ("vec-1", "4.005, 7", True),  # inside the numeric tolerance
        ("vec-1", "7, 4", False),  # ordered problem
        ("vec-1", "4, 7, 9", False),  # extra value
        ("eig-1", "3 and 2", True),  # unordered problem
        ("eig-1", "lambda1 = 2, lambda2 = 3", True),
        ("dot-3", "4/2", True),
        ("bs-1b", "four", True),
        ("bo-1", "O(n)", True),
        ("bo-1", "linear", True),
        ("bo-1b", "O(n)", False),
        ("bo-2", "O(3n^2)", True),
        ("ms-2", "n log n", True),
        ("mm-1b", "No, the inner dimensions differ", True),
        ("mm-1b", "not possible", True),
        ("mm-1b", "yes", False),
        ("bs-1", "sorted", True),
        ("bs-1", "in sorted order", True),
        ("bs-1", "not sorted", False),  # negation guard
        ("bs-1", "unsorted", False),
    ],
)
def test_layer1_exact(pid, answer, ok):
    parsed = parse(P(pid), answer)
    result = layer_exact(P(pid), parsed)
    assert result["layer"] == 1 and result["name"] == "exact_match"
    assert result["passed"] is ok
    assert result["score"] == (1.0 if ok else 0.0)


# ---- layer 2: partial credit -------------------------------------------------

def test_layer2_numeric_partial():
    p = P("mm-3")
    parsed = parse(p, "19, 22, 43, 51")
    r = layer_partial(p, parsed, exact=False)
    assert r["name"] == "partial_credit"
    assert r["score"] == pytest.approx(0.75)


def test_layer2_unordered_partial():
    p = P("eig-1")
    r = layer_partial(p, parse(p, "3"), exact=False)
    assert r["score"] == pytest.approx(0.5)


def test_layer2_text_key_points():
    p = P("eig-1b")
    one = layer_partial(p, parse(p, "v is scaled by A, a scalar multiple of itself"), exact=False)
    assert one["score"] == pytest.approx(0.5)
    both = layer_partial(p, parse(p, "A scales v by a scalar multiple and keeps its direction"), exact=False)
    assert both["score"] == 1.0
    none = layer_partial(p, parse(p, "bananas"), exact=False)
    assert none["score"] == 0.0


def test_partial_credit_changes_the_composite_score():
    half = ev("mm-3", "19, 22, 0, 0")
    none = ev("mm-3", "0, 0, 0, 0")
    assert half.score > none.score


# ---- layer 3: reasoning alignment --------------------------------------------

def test_layer3_reasoning_alignment_uses_answer_and_reasoning():
    p = P("dot-1")
    none = layer_reasoning(p, "11", "")
    full = layer_reasoning(p, "11", "multiply each component, then add the sum of the product terms")
    assert none["score"] == 0.0
    assert full["score"] == 1.0 and full["matched_terms"]
    partial = layer_reasoning(p, "11", "multiply and add")  # 2 of the 3 terms needed for full alignment
    assert partial["score"] == pytest.approx(2 / 3, abs=1e-3)


def test_reasoning_lifts_score_for_a_correct_answer():
    bare = ev("dot-1", "11")
    reasoned = ev("dot-1", "11", "multiply each component then add the sum of products")
    assert bare.passed and reasoned.passed
    assert reasoned.score > bare.score


# ---- layer 4: error typing -----------------------------------------------------

@pytest.mark.parametrize(
    "pid,answer,expected",
    [
        ("vec-1", "4, 7", "none"),
        # conceptual_error
        ("vec-1", "3, 10", "conceptual_error"),
        ("dot-1", "100", "conceptual_error"),
        ("bo-1b", "O(n)", "conceptual_error"),
        ("mm-1b", "yes", "conceptual_error"),
        # calculation_error
        ("dot-2", "16", "calculation_error"),
        ("dot-1", "12", "calculation_error"),
        ("mm-3", "19, 22, 43, 51", "calculation_error"),
        ("bs-3", "19", "calculation_error"),
        # misinterpretation
        ("mm-1", "4, 2", "misinterpretation"),
        ("bs-2", "12", "misinterpretation"),
        ("vec-1", "hello", "misinterpretation"),
        ("bo-1", "banana", "misinterpretation"),
        ("ms-1", "3", "misinterpretation"),
        # incomplete
        ("eig-1", "2", "incomplete"),
        ("vec-1", "I don't know", "incomplete"),
        ("eig-1b", "A v is a scalar multiple of v", "incomplete"),
    ],
)
def test_layer4_error_typing(pid, answer, expected):
    e = ev(pid, answer)
    l4 = layer(e, "error_typing")
    assert l4["layer"] == 4
    assert l4["error_type"] == expected
    assert e.error_type == expected
    assert l4["detail"]


# ---- layer 5: confidence delta -------------------------------------------------

def test_layer5_confidence_moves_toward_score():
    up = layer_confidence(0.2, 1.0, 0)
    down = layer_confidence(0.9, 0.0, 5)
    assert up["after"] > up["before"] and up["delta"] > 0
    assert down["after"] < down["before"] and down["delta"] < 0
    assert up["name"] == "confidence_delta" and up["layer"] == 5


def test_layer5_learning_rate_slows_with_experience_and_clamps():
    early = update_confidence(0.2, 1.0, 0)
    late = update_confidence(0.2, 1.0, 10)
    assert early[0] > late[0]
    assert update_confidence(0.99, 1.0, 0)[0] <= 1.0
    assert update_confidence(0.01, 0.0, 0)[0] >= 0.0


def test_layer5_is_reported_in_evaluation():
    e = ev("vec-1", "4, 7", before=0.3, attempts=0)
    l5 = layer(e, "confidence_delta")
    assert l5["before"] == 0.3
    assert e.confidence_after == l5["after"]
    assert l5["delta"] == pytest.approx(l5["after"] - l5["before"], abs=1e-3)


# ---- composite + learning signal ---------------------------------------------------

def test_all_five_layers_present_in_order():
    e = ev("vec-1", "3, 10")
    assert [l["layer"] for l in e.layers] == [1, 2, 3, 4, 5]
    assert [l["name"] for l in e.layers] == [
        "exact_match", "partial_credit", "reasoning_alignment", "error_typing", "confidence_delta"
    ]


def test_pass_threshold_and_scores_are_ordered():
    perfect = ev("vec-1", "4, 7", "add each matching component, the sum")
    bare = ev("vec-1", "4, 7")
    wrong = ev("vec-1", "3, 10")
    assert perfect.score > bare.score >= 0.7 > wrong.score
    assert perfect.passed and bare.passed and not wrong.passed


def test_learning_signal_shape_and_logic():
    weak = learning_signal("vectors", ev("vec-1", "3, 10", before=0.7))
    assert set(weak) >= {"weak_concept", "retry_recommended"}
    assert weak["weak_concept"] is True and weak["retry_recommended"] is True
    fine = learning_signal("vectors", ev("vec-1", "4, 7", "add each component sum", before=0.7))
    assert fine["weak_concept"] is False and fine["retry_recommended"] is False
    slip = learning_signal("vectors", ev("dot-1", "12", before=0.7))
    assert slip["retry_recommended"] is True


# ---- problem bank integrity ----------------------------------------------------------

ALL = CUR.all_problems()


def test_bank_has_every_concept_at_every_difficulty():
    for concept in CUR.concepts.values():
        assert {p.difficulty for p in concept.problems} == {1, 2, 3}, concept.id


@pytest.mark.parametrize("problem", ALL, ids=[p.id for p in ALL])
def test_bank_correct_answers_pass_and_signatures_type_as_declared(problem):
    from ale.research.simulate import correct_answer

    answer, reasoning = correct_answer(problem)
    good = evaluate(problem, answer, reasoning, confidence_before=0.3, attempts=0)
    assert good.passed, (problem.id, answer, good.layers)
    assert good.error_type == "none"
    assert good.score >= 0.9

    assert any(s.type == "conceptual_error" for s in problem.signatures), "needs a conceptual signature"
    from ale.research.simulate import wrong_answer

    for sig in problem.signatures:
        text = wrong_answer(problem, sig.type)
        bad = evaluate(problem, text, "", confidence_before=0.3, attempts=0)
        assert not bad.passed, (problem.id, text)
        assert bad.error_type in {s.type for s in problem.signatures}, (problem.id, text, bad.error_type)
    for sig in problem.signatures:
        if sig.numbers is not None or sig.forms is not None:
            text = ", ".join(str(int(x)) if float(x).is_integer() else str(x) for x in sig.numbers) if sig.numbers else sig.example
            assert evaluate(problem, text, "", confidence_before=0.3, attempts=0).error_type == sig.type, (problem.id, text)
