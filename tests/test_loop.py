"""The adaptive loop end to end on the fixture corpus, plus behavior of simulated learners."""

import pytest

from ale.research.simulate import PERSONAS, correct_answer, run_all, run_persona, wrong_answer


def run_one(tutor, user, topic, name):
    return run_persona(PERSONAS[name], tutor, user, topic)


def test_service_loop_start_lesson_problem_answer_next_progress(tutor):
    state = tutor.start_topic("ada", "linear algebra")
    assert state["phase"] == "needs_lesson" and state["concept"] == "vectors"

    lesson = tutor.get_lesson("ada")
    assert lesson["citations"] and all(c["score"] > 0 for c in lesson["citations"])

    issued = tutor.get_problem("ada")
    bank = tutor.curriculum.problem(issued["bank_id"])
    answer, reasoning = correct_answer(bank)
    result = tutor.submit_answer("ada", issued["problem_id"], answer, reasoning)

    assert [l["layer"] for l in result["evaluation"]["layers"]] == [1, 2, 3, 4, 5]
    assert result["correct"] and result["error_type"] == "none"
    assert set(result["learning_signal"]) >= {"weak_concept", "retry_recommended"}
    assert result["next_step"]["action"] in {"advance", "practice_harder", "repeat", "reteach"}
    assert result["memory"]["delta"] > 0

    progress = tutor.progress("ada")
    assert next(c for c in progress["concepts"] if c["concept"] == "vectors")["confidence"] == result["memory"]["confidence_after"]


@pytest.mark.parametrize(
    "behavior,action,rule",
    [
        ("conceptual_error", "reteach", "conceptual_error"),
        ("calculation_error", "repeat", "calculation_error"),
        ("incomplete", "repeat", "failed_attempt"),
    ],
)
def test_first_wrong_answer_routes_by_error_type(tutor, behavior, action, rule):
    tutor.start_topic("ada", "linear algebra")
    issued = tutor.get_problem("ada")
    bank = tutor.curriculum.problem(issued["bank_id"])
    r = tutor.submit_answer("ada", issued["problem_id"], wrong_answer(bank, behavior))
    assert r["error_type"] == behavior
    assert (r["next_step"]["action"], r["next_step"]["rule"]) == (action, rule)


def test_misinterpretation_routes_to_reteach(tutor):
    tutor.start_topic("ada", "algorithms")
    issued = tutor.get_problem("ada")
    bank = tutor.curriculum.problem(issued["bank_id"])
    r = tutor.submit_answer("ada", issued["problem_id"], "banana")
    assert bank.kind == "complexity" and r["error_type"] == "misinterpretation"
    assert r["next_step"]["action"] == "reteach"


def test_three_slips_in_a_row_trigger_reteach(tutor):
    tutor.start_topic("ada", "linear algebra")
    actions = []
    for _ in range(3):
        issued = tutor.get_problem("ada")
        bank = tutor.curriculum.problem(issued["bank_id"])
        r = tutor.submit_answer("ada", issued["problem_id"], wrong_answer(bank, "calculation_error"))
        assert r["error_type"] == "calculation_error"
        actions.append((r["next_step"]["action"], r["next_step"]["rule"]))
        tutor.get_lesson("ada")
    assert actions == [("repeat", "calculation_error"), ("repeat", "calculation_error"), ("reteach", "failure_streak")]
    assert tutor.state("ada")["lesson_level"] == "easy"
    assert tutor.progress("ada")["concepts"][0]["consecutive_failures"] == 0  # streak was acted on


def test_confidence_walks_the_documented_bands(tutor):
    tutor.start_topic("ada", "linear algebra")
    seen = []
    for _ in range(2):
        issued = tutor.get_problem("ada")
        answer, reasoning = correct_answer(tutor.curriculum.problem(issued["bank_id"]))
        r = tutor.submit_answer("ada", issued["problem_id"], answer, reasoning)
        seen.append((r["memory"]["confidence_after"], r["next_step"]["action"]))
    (c1, a1), (c2, a2) = seen
    assert 0.5 <= c1 < 0.8 and a1 == "practice_harder"
    assert c2 >= 0.8 and a2 == "advance"
    assert tutor.state("ada")["concept"] == "dot_product" and tutor.state("ada")["difficulty"] == 1


def test_practice_harder_raises_difficulty_and_serves_a_harder_problem(tutor):
    tutor.start_topic("ada", "linear algebra")
    first = tutor.get_problem("ada")
    answer, reasoning = correct_answer(tutor.curriculum.problem(first["bank_id"]))
    tutor.submit_answer("ada", first["problem_id"], answer, reasoning)
    second = tutor.get_problem("ada")
    assert second["difficulty"] == first["difficulty"] + 1


def test_reteach_serves_a_different_lesson_at_an_easier_level(tutor):
    tutor.start_topic("ada", "linear algebra")
    standard = tutor.get_lesson("ada")
    p = tutor.get_problem("ada")
    tutor.submit_answer("ada", p["problem_id"], wrong_answer(tutor.curriculum.problem(p["bank_id"]), "conceptual_error"))
    easy = tutor.get_lesson("ada")
    assert easy["level"] == "easy" and standard["level"] == "standard"
    assert len(easy["citations"]) < len(standard["citations"])
    assert {c["chunk_id"] for c in easy["citations"]} != {c["chunk_id"] for c in standard["citations"]}
    assert all(c["section"].startswith("Vectors") for c in easy["citations"])
    assert "easier level" in easy["adaptation_note"]


# ---- simulated learners: behavior, not just correctness -----------------------------------------

@pytest.fixture(scope="module")
def sims(tmp_path_factory):
    results = run_all("linear algebra", db=tmp_path_factory.mktemp("sim") / "s.db")
    return {r["persona"]: r for r in results}


def test_mastery_learner_finishes_fast_without_remediation(sims):
    r = sims["mastery"]
    assert r["completed"] and r["steps"] == 8
    assert set(r["actions"]) == {"advance", "practice_harder"}


def test_slower_learners_take_more_steps_than_mastery(sims):
    assert sims["mastery"]["steps"] < sims["confused"]["steps"] < sims["careless"]["steps"]


def test_careless_learner_gets_practice_not_reteach(sims):
    r = sims["careless"]
    assert r["completed"]
    slips = [t for t in r["trajectory"] if t["error_type"] == "calculation_error"]
    assert slips and all(t["action"] == "repeat" for t in slips)
    assert "reteach" not in r["actions"]


def test_confused_learner_is_reteached_once_per_concept_and_recovers(sims):
    r = sims["confused"]
    assert r["completed"] and r["actions"]["reteach"] == 4
    for t in r["trajectory"]:
        if t["action"] == "reteach":
            assert t["error_type"] in {"conceptual_error", "misinterpretation"} and t["lesson_level"] == "easy"


def test_struggling_learner_never_advances_and_is_reteached_on_streaks(sims):
    r = sims["struggling"]
    assert not r["completed"] and "advance" not in r["actions"]
    streaks = [t for t in r["trajectory"] if t["rule"] == "failure_streak"]
    assert streaks and [t["step"] for t in streaks][:2] == [3, 6]
    assert all(t["confidence"] < 0.5 for t in r["trajectory"])
