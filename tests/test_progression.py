"""Progression engine decision tests."""

from __future__ import annotations

from engine.memory import MemoryStore
from engine.progression import EvaluationOutcome, ProgressionEngine


def test_conceptual_error_triggers_reteach(tmp_path, monkeypatch) -> None:
    db = tmp_path / "progress.db"
    monkeypatch.setattr("engine.memory.USER_PROGRESS_DB_PATH", db)

    memory = MemoryStore(db)
    prog = ProgressionEngine(memory)
    user_id = "prog_test"
    topic = "math"
    concept = "eigenvalues"

    memory.ensure_user_topic(user_id, topic, current_concept=concept)
    for _ in range(3):
        memory.update_progress(user_id, topic, concept, correct=False)

    outcome = EvaluationOutcome(
        concept=concept,
        is_correct=False,
        score=0.0,
        error_type="conceptual_error",
    )
    decision = prog.decide_from_evaluation(user_id, topic, outcome)
    assert decision.action in ("reteach", "repeat")
    assert decision.difficulty == "beginner"


def test_high_confidence_advances(tmp_path, monkeypatch) -> None:
    db = tmp_path / "progress2.db"
    monkeypatch.setattr("engine.memory.USER_PROGRESS_DB_PATH", db)

    memory = MemoryStore(db)
    prog = ProgressionEngine(memory)
    user_id = "prog_test2"
    topic = "math"
    concept = "vectors"

    memory.ensure_user_topic(user_id, topic, current_concept=concept)
    for _ in range(8):
        memory.update_progress(user_id, topic, concept, correct=True, score=1.0)

    decision = prog.decide_next_step(user_id, concept, topic)
    assert decision.action == "advance"
