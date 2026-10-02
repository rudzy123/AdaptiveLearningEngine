"""Tutor: the service object that runs the adaptive loop and owns all state transitions.

    start_topic -> get_lesson -> get_problem -> submit_answer -> (next step applied) -> progress

Every transition is written to SQLite before it is returned, so a new process (or a page refresh)
reconstructs the exact same state from `state()` / `progress()`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ale.engine.config import INITIAL_CONFIDENCE, MASTERED_CONFIDENCE, default_db_path
from ale.engine.curriculum import Curriculum, load_curriculum
from ale.engine.errors import TutorError
from ale.engine.evaluation import evaluate, learning_signal
from ale.engine.ingest import ensure_fixture
from ale.engine.lesson import build_lesson
from ale.engine.problems import public_problem, select_problem
from ale.engine.progression import Decision, StepInput, decide
from ale.engine.retrieval import Retriever
from ale.engine.store import Session, Store, now

USER_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
MAX_ANSWER_CHARS = 2000
ACTION_LABELS = {
    "advance": "Advance",
    "practice_harder": "Practice harder",
    "repeat": "Repeat",
    "reteach": "Reteach",
}


def _check_user(user_id: str) -> str:
    if not isinstance(user_id, str) or not USER_ID_RE.match(user_id):
        raise TutorError("user_id must be 1-64 characters: letters, digits, '_', '.', '-'", "validation_error", 422)
    return user_id


class Tutor:
    def __init__(self, db: str | Path | Store | None = None, curriculum: Curriculum | None = None) -> None:
        self.store = db if isinstance(db, Store) else Store(db or default_db_path())
        self.curriculum = curriculum or load_curriculum()
        ensure_fixture(self.store)
        self._retriever: Retriever | None = None
        self._retriever_version = -1

    # infrastructure -------------------------------------------------------
    def retriever(self) -> Retriever:
        version = self.store.chunks_version()
        if self._retriever is None or version != self._retriever_version:
            self._retriever = Retriever.from_store(self.store)
            self._retriever_version = version
        return self._retriever

    def _session(self, user_id: str) -> Session:
        _check_user(user_id)
        s = self.store.get_session(user_id)
        if s is None:
            raise TutorError(f"No active session for '{user_id}'. Start a topic first.", "no_session", 404)
        return s

    # topics / search ------------------------------------------------------
    def topics(self) -> list[dict[str, Any]]:
        return [
            {
                "id": t.id,
                "title": t.title,
                "concepts": [{"id": c, "title": self.curriculum.concepts[c].title} for c in t.concepts],
            }
            for t in self.curriculum.topics.values()
        ]

    def search(self, query: str, k: int = 4) -> list[dict[str, Any]]:
        return [h.citation(i + 1) for i, h in enumerate(self.retriever().search(query, k=k))]

    # 1. start a topic -----------------------------------------------------
    def start_topic(self, user_id: str, topic: str, restart: bool = False) -> dict[str, Any]:
        _check_user(user_id)
        t = self.curriculum.find_topic(topic)
        if t is None:
            names = ", ".join(x.title for x in self.curriculum.topics.values())
            raise TutorError(f"Unknown topic '{topic}'. Available topics: {names}.", "unknown_topic", 404)
        existing = self.store.get_session(user_id)
        resumed = bool(existing and existing.topic == t.id and not restart)
        if not resumed:
            memory = self.store.all_memory(user_id)
            first = t.concepts[0]
            if not restart:
                first = next(
                    (c for c in t.concepts if memory.get(c) is None or memory[c].confidence < MASTERED_CONFIDENCE),
                    t.concepts[0],
                )
            ts = now()
            self.store.save_session(
                Session(user_id, t.id, first, 1, "standard", "active", None, None, None, ts, ts)
            )
        view = self.state(user_id)
        view["resumed"] = resumed
        return view

    # 2. lesson ------------------------------------------------------------
    def get_lesson(self, user_id: str) -> dict[str, Any]:
        s = self._session(user_id)
        if s.lesson is not None:
            return s.lesson
        concept = self.curriculum.concepts[s.concept]
        memory = self.store.get_memory(user_id, s.concept, INITIAL_CONFIDENCE)
        if memory.attempts == 0:
            memory.confidence = 0.0
        lesson = build_lesson(
            self.retriever(),
            concept,
            level=s.lesson_level,
            difficulty=s.difficulty,
            memory=memory,
            previous_chunk_ids=self.store.lesson_chunk_ids(user_id, s.concept),
        )
        s.lesson = lesson
        self.store.save_session(s)
        self.store.record_lesson(user_id, s.concept, s.lesson_level, [c["chunk_id"] for c in lesson["citations"]])
        return lesson

    # 3. problem -----------------------------------------------------------
    def get_problem(self, user_id: str) -> dict[str, Any]:
        s = self._session(user_id)
        if s.status == "completed":
            raise TutorError("This topic is complete. Restart it or start another topic.", "topic_complete", 409)
        if s.problem_id:
            issued = self.store.get_issued(s.problem_id)
            return public_problem(self.curriculum.problem(issued["bank_id"]), s.problem_id)
        concept = self.curriculum.concepts[s.concept]
        problem = select_problem(concept, s.difficulty, self.store.issue_counts(user_id, s.concept))
        problem_id = self.store.issue_problem(user_id, s.concept, problem.id, problem.difficulty)
        s.problem_id = problem_id
        s.last_result = None  # a new problem replaces the previous result on screen
        self.store.save_session(s)
        return public_problem(problem, problem_id)

    # 4. answer ------------------------------------------------------------
    def submit_answer(self, user_id: str, problem_id: str, answer: str, reasoning: str = "") -> dict[str, Any]:
        s = self._session(user_id)
        if not isinstance(answer, str) or not answer.strip():
            raise TutorError("answer must not be empty", "validation_error", 422)
        if len(answer) > MAX_ANSWER_CHARS or len(reasoning or "") > MAX_ANSWER_CHARS:
            raise TutorError(f"answer and reasoning are limited to {MAX_ANSWER_CHARS} characters", "validation_error", 422)
        if not s.problem_id:
            raise TutorError("There is no open problem. Request one first.", "no_active_problem", 409)
        if s.problem_id != problem_id:
            raise TutorError("problem_id does not match the open problem.", "problem_mismatch", 409)

        issued = self.store.get_issued(problem_id)
        problem = self.curriculum.problem(issued["bank_id"])
        mem = self.store.get_memory(user_id, s.concept, INITIAL_CONFIDENCE)

        ev = evaluate(problem, answer, reasoning or "", confidence_before=mem.confidence, attempts=mem.attempts)

        before = mem.confidence
        mem.confidence = ev.confidence_after
        mem.attempts += 1
        mem.correct += 1 if ev.passed else 0
        mem.consecutive_failures = 0 if ev.passed else mem.consecutive_failures + 1
        mem.last_error_type = ev.error_type
        mem.last_score = ev.score

        decision: Decision = decide(
            StepInput(
                concept=s.concept,
                difficulty=s.difficulty,
                confidence=mem.confidence,
                error_type=ev.error_type,
                passed=ev.passed,
                consecutive_failures=mem.consecutive_failures,
                next_concept=self.curriculum.next_concept(s.concept),
            )
        )
        failures_at_decision = mem.consecutive_failures
        if decision.reteach:
            mem.consecutive_failures = 0  # the streak has been acted on

        signal = learning_signal(s.concept, ev)
        next_step = decision.to_dict() | {
            "label": ACTION_LABELS[decision.action],
            "next_concept_title": self.curriculum.concepts[decision.next_concept].title,
            "consecutive_failures": failures_at_decision,
        }
        result = {
            "problem_id": problem_id,
            "bank_id": problem.id,
            "prompt": problem.prompt,
            "concept": s.concept,
            "answer": answer,
            "reasoning": reasoning or "",
            "correct": ev.passed,
            "score": ev.score,
            "error_type": ev.error_type,
            "evaluation": ev.to_dict(),
            "learning_signal": signal,
            "memory": {
                "concept": s.concept,
                "confidence_before": before,
                "confidence_after": mem.confidence,
                "delta": ev.layers[4]["delta"],
                "attempts": mem.attempts,
                "correct": mem.correct,
                "consecutive_failures": mem.consecutive_failures,
            },
            "next_step": next_step,
        }

        # Apply the decision to the session.
        s.problem_id = None
        s.last_result = result
        s.difficulty = decision.difficulty
        s.lesson_level = decision.lesson_level
        if decision.topic_complete:
            s.status = "completed"  # stay on the last concept; its lesson remains visible
        elif decision.action == "advance":
            s.concept = decision.next_concept
            s.lesson = None
        elif decision.action == "reteach":
            s.lesson = None

        with self.store.tx() as conn:
            self.store.save_memory(mem, conn)
            self.store.close_problem(conn, problem_id)
            self.store.insert_attempt(
                conn,
                user_id=user_id, concept=result["concept"], problem_id=problem_id, bank_id=problem.id,
                answer=answer, reasoning=reasoning or "", score=ev.score, passed=int(ev.passed),
                error_type=ev.error_type, confidence_before=before, confidence_after=mem.confidence,
                action=decision.action, evaluation_json=json.dumps(result["evaluation"]),
            )
            self.store.save_session(s, conn)
        return result

    # 5. progress / state --------------------------------------------------
    def progress(self, user_id: str) -> dict[str, Any]:
        _check_user(user_id)
        memory = self.store.all_memory(user_id)
        session = self.store.get_session(user_id)
        topics = []
        concepts = []
        for t in self.curriculum.topics.values():
            rows = []
            for cid in t.concepts:
                m = memory.get(cid)
                row = {
                    "concept": cid,
                    "title": self.curriculum.concepts[cid].title,
                    "topic": t.id,
                    "confidence": round(m.confidence, 3) if m else 0.0,
                    "attempts": m.attempts if m else 0,
                    "correct": m.correct if m else 0,
                    "consecutive_failures": m.consecutive_failures if m else 0,
                    "last_error_type": m.last_error_type if m else "none",
                    "mastered": bool(m and m.confidence >= MASTERED_CONFIDENCE),
                    "current": bool(session and session.concept == cid),
                }
                rows.append(row)
            concepts.extend(rows)
            topics.append(
                {
                    "id": t.id,
                    "title": t.title,
                    "mean_confidence": round(sum(r["confidence"] for r in rows) / len(rows), 3),
                    "mastered": sum(r["mastered"] for r in rows),
                    "total": len(rows),
                }
            )
        return {
            "user_id": user_id,
            "topic": session.topic if session else None,
            "current_concept": session.concept if session else None,
            "topics": topics,
            "concepts": concepts,
            "recent_attempts": self.store.recent_attempts(user_id),
        }

    def state(self, user_id: str) -> dict[str, Any]:
        """Everything a client needs to redraw the screen after a refresh or restart."""
        s = self._session(user_id)
        if s.status == "completed":
            phase = "completed"
        elif s.problem_id:
            phase = "awaiting_answer"
        elif s.lesson is None:
            phase = "needs_lesson"
        else:
            phase = "needs_problem"
        problem = None
        if s.problem_id:
            issued = self.store.get_issued(s.problem_id)
            problem = public_problem(self.curriculum.problem(issued["bank_id"]), s.problem_id)
        concept = self.curriculum.concepts[s.concept]
        topic = self.curriculum.topics[s.topic]
        return {
            "user_id": user_id,
            "topic": topic.id,
            "topic_title": topic.title,
            "concept": concept.id,
            "concept_title": concept.title,
            "difficulty": s.difficulty,
            "lesson_level": s.lesson_level,
            "status": s.status,
            "phase": phase,
            "lesson": s.lesson,
            "problem": problem,
            "last_result": s.last_result,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
        }
