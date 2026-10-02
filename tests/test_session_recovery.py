"""State survives process restarts: every phase of the loop is reconstructed from SQLite."""

import pytest

from ale.engine import Tutor, TutorError
from ale.research.simulate import PERSONAS, correct_answer, run_persona


def reopen(db_path):
    return Tutor(db_path)  # a fresh object with no cached state, as a new process would have


def test_session_lesson_problem_result_and_memory_survive_restart(db_path):
    t1 = Tutor(db_path)
    t1.start_topic("ada", "linear algebra")
    assert reopen(db_path).state("ada") == t1.state("ada")

    lesson = t1.get_lesson("ada")
    assert reopen(db_path).get_lesson("ada") == lesson  # stable, not regenerated
    assert reopen(db_path).state("ada")["phase"] == "needs_problem"

    problem = t1.get_problem("ada")
    t2 = reopen(db_path)
    assert t2.get_problem("ada") == problem
    assert t2.state("ada")["phase"] == "awaiting_answer"

    answer, reasoning = correct_answer(t2.curriculum.problem(problem["bank_id"]))
    result = t2.submit_answer("ada", problem["problem_id"], answer, reasoning)

    t3 = reopen(db_path)
    state = t3.state("ada")
    assert state["last_result"] == result
    assert state["phase"] == "needs_problem"  # repeat/practice keep the lesson
    progress = t3.progress("ada")
    vectors = next(c for c in progress["concepts"] if c["concept"] == "vectors")
    assert vectors["confidence"] == result["memory"]["confidence_after"]
    assert vectors["attempts"] == 1 and vectors["correct"] == 1
    assert progress["recent_attempts"][0]["action"] == result["next_step"]["action"]


def test_progress_after_restart_matches_exactly_for_a_long_session(db_path):
    t1 = Tutor(db_path)
    run_persona(PERSONAS["confused"], t1, "ben", "linear algebra")
    assert reopen(db_path).progress("ben") == t1.progress("ben")
    assert reopen(db_path).state("ben")["status"] == "completed"


def test_reteach_clears_lesson_and_it_regenerates_after_restart(db_path):
    t = Tutor(db_path)
    t.start_topic("ada", "linear algebra")
    t.get_lesson("ada")
    p = t.get_problem("ada")
    t.submit_answer("ada", p["problem_id"], "3, 10")  # conceptual error -> reteach
    t2 = reopen(db_path)
    assert t2.state("ada")["phase"] == "needs_lesson"
    assert t2.get_lesson("ada")["level"] == "easy"


def test_resume_restart_and_topic_switch(db_path):
    t = Tutor(db_path)
    t.start_topic("ada", "linear algebra")
    p = t.get_problem("ada")
    t.submit_answer("ada", p["problem_id"], "4, 7", "add each component sum")
    t.get_problem("ada")
    assert t.state("ada")["difficulty"] == 2

    resumed = reopen(db_path).start_topic("ada", "linear algebra")
    assert resumed["resumed"] is True and resumed["difficulty"] == 2 and resumed["phase"] == "awaiting_answer"

    restarted = t.start_topic("ada", "linear algebra", restart=True)
    assert restarted["resumed"] is False and restarted["difficulty"] == 1 and restarted["concept"] == "vectors"

    switched = t.start_topic("ada", "algorithms")
    assert switched["topic"] == "algorithms" and switched["concept"] == "big_o"
    # confidence earned in the first topic is still there
    vectors = next(c for c in t.progress("ada")["concepts"] if c["concept"] == "vectors")
    assert vectors["confidence"] > 0.5


def test_new_topic_starts_at_first_unmastered_concept(db_path):
    t = Tutor(db_path)
    run_persona(PERSONAS["mastery"], t, "ada", "linear algebra")
    t.start_topic("ada", "algorithms")
    run_persona(PERSONAS["mastery"], t, "ada", "algorithms")
    assert t.state("ada")["status"] == "completed"
    again = t.start_topic("ada", "linear algebra")
    assert again["concept"] == "vectors"  # everything mastered -> start from the top, as a review


def test_users_are_isolated(db_path):
    t = Tutor(db_path)
    t.start_topic("ada", "linear algebra")
    t.start_topic("ben", "algorithms")
    p = t.get_problem("ada")
    t.submit_answer("ada", p["problem_id"], "3, 10")
    assert t.progress("ben")["concepts"][0]["attempts"] == 0
    assert t.state("ben")["topic"] == "algorithms"
    with pytest.raises(TutorError) as exc:
        t.submit_answer("ben", p["problem_id"], "4, 7")
    assert exc.value.code in {"no_active_problem", "problem_mismatch"}


def test_errors_are_typed(tutor):
    with pytest.raises(TutorError) as e:
        tutor.get_lesson("nobody")
    assert (e.value.code, e.value.status) == ("no_session", 404)
    with pytest.raises(TutorError) as e:
        tutor.start_topic("bad id", "algorithms")
    assert e.value.code == "validation_error"
    tutor.start_topic("ada", "algorithms")
    with pytest.raises(TutorError) as e:
        tutor.submit_answer("ada", "p_nope", "x")
    assert e.value.code == "no_active_problem"


def test_completed_topic_has_no_more_problems(tutor):
    run_persona(PERSONAS["mastery"], tutor, "ada", "algorithms")
    assert tutor.state("ada")["phase"] == "completed"
    with pytest.raises(TutorError) as e:
        tutor.get_problem("ada")
    assert e.value.code == "topic_complete"


def test_in_memory_database_is_refused():
    from ale.engine.store import Store

    with pytest.raises(ValueError):
        Store(":memory:")
