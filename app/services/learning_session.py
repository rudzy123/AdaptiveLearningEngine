"""
LearningSession — production orchestrator for the adaptive learning API.

All business logic for HTTP endpoints lives here. Routes must not call engine
modules directly.
"""

from __future__ import annotations

import logging
from typing import Any

from app.learning_loop import AdaptiveLearningLoop
from app.services.exceptions import ServiceError
from app.services.rag_service import RagService
from app.services.validation import (
    validate_answer,
    validate_level,
    validate_topic,
    validate_user_id,
)
from config import CONFIDENCE_PRACTICE
from data.session_repository import SessionRepository, SessionState
from engine.concepts import ConceptRegistry
from engine.curriculum import CurriculumService
from engine.evaluation import AnswerEvaluator
from engine.memory import MemoryStore
from engine.problem_generator import ProblemGenerator
from engine.progression import ProgressionEngine
from engine.user_state import LearnerLevel, UserState
from generation.lesson import generate_lesson as build_lesson_from_engine

logger = logging.getLogger(__name__)

DIFFICULTY_SEQUENCE: list[LearnerLevel] = ["beginner", "intermediate", "advanced"]
DIFFICULTY_API = {"beginner": "easy", "intermediate": "medium", "advanced": "hard"}
ACTION_API_MAP = {
    "advance": "advance",
    "repeat": "repeat",
    "reteach": "reteach",
    "review_previous": "review",
    "practice_harder": "repeat",
}


class LearningSession:
    """
    Stateful learning orchestrator keyed by user_id.

    Every public method: load session -> mutate -> save session.
    """

    def __init__(
        self,
        *,
        sessions: SessionRepository | None = None,
        memory: MemoryStore | None = None,
        concepts: ConceptRegistry | None = None,
        rag: RagService | None = None,
    ) -> None:
        self.sessions = sessions or SessionRepository()
        self.memory = memory or MemoryStore()
        self.concepts = concepts or ConceptRegistry()
        self.curriculum = CurriculumService(self.concepts)
        self.progression = ProgressionEngine(self.memory, self.concepts)
        self.evaluator = AnswerEvaluator(self.memory, self.progression)
        self.problems = ProblemGenerator()
        self.rag = rag or RagService()

    # ------------------------------------------------------------------ state
    def _load(self, user_id: str) -> SessionState:
        state = self.sessions.load(user_id)
        if not state or not state.topic:
            raise ServiceError(
                "No active session. Call POST /start_topic first.", 404
            )
        return state

    def _save(self, state: SessionState) -> None:
        state.current_concept = (
            state.concepts[state.concept_index]
            if state.concepts and state.concept_index < len(state.concepts)
            else state.current_concept
        )
        self.sessions.save(state)

    def _build_user_state(self, state: SessionState) -> UserState:
        us = self.progression.build_user_state(state.user_id, state.topic)
        us.current_concept = state.current_concept
        us.difficulty = state.level  # type: ignore[assignment]
        us.focus_concepts = list(
            dict.fromkeys([state.current_concept, *us.weak_concepts])
        )
        return us

    @staticmethod
    def resolve_topic(raw: str) -> tuple[str, str]:
        canonical = AdaptiveLearningLoop.resolve_topic(raw.strip().lower())
        label = raw.strip() or canonical
        if canonical == "math" and "linear" in raw.lower():
            label = "linear algebra"
        return canonical, label

    # -------------------------------------------------------------- endpoints
    def start_topic(
        self,
        user_id: str,
        topic: str,
        level: str = "beginner",
        *,
        max_concepts: int = 10,
        problems_per_concept: int = 3,
    ) -> dict[str, Any]:
        """Initialize topic and persist session."""
        uid = validate_user_id(user_id)
        topic_raw = validate_topic(topic)
        level_norm = validate_level(level)
        canonical, label = self.resolve_topic(topic_raw)

        concept_list = self.curriculum.get_concepts_for_topic(canonical)
        if not concept_list:
            concept_list = self.concepts.get_concepts_for_topic(canonical)
        concept_list = concept_list[:max_concepts]
        if not concept_list:
            raise ServiceError(f"No concepts for topic '{topic_raw}'", 404)

        self.memory.ensure_user_topic(
            uid,
            canonical,
            level=level_norm,  # type: ignore[arg-type]
            current_concept=concept_list[0],
        )

        state = SessionState(
            user_id=uid,
            topic=canonical,
            topic_label=label,
            level=level_norm,
            concepts=concept_list,
            concept_index=0,
            problem_index=0,
            problems_per_concept=problems_per_concept,
            phase="lesson",
            current_concept=concept_list[0],
        )
        self._save(state)

        return {
            "message": "Topic initialized",
            "current_concept": concept_list[0],
            "topic": canonical,
            "topic_label": label,
        }

    def get_lesson(self, user_id: str) -> dict[str, Any]:
        """Generate lesson with RAG chunks and citations."""
        uid = validate_user_id(user_id)
        state = self._load(uid)
        concept = state.current_concept

        user_state = self._build_user_state(state)
        weak_records = self.memory.get_weak_areas(uid, state.topic)
        weak_ids = tuple(p.concept for p in weak_records)

        rag_ctx = self.rag.retrieve_for_concept(
            concept, topic=state.topic, weak_concepts=weak_ids
        )
        citations = [c.citation() for c in rag_ctx.chunks]
        intro = (
            f"## {self.concepts.label(concept)}\n\n"
            f"Level: {state.level} · Topic: {state.topic_label or state.topic}"
        )

        lesson_text = ""
        try:
            generated = build_lesson_from_engine(user_state)
            lesson_text = generated.render()
            if citations:
                lesson_text += "\n\n### References\n" + "\n".join(
                    f"- {c}" for c in citations
                )
        except FileNotFoundError:
            lesson_text = rag_ctx.compose_lesson_text(intro)
            if not rag_ctx.chunks:
                lesson_text = (
                    f"{intro}\n\nStudy {self.concepts.label(concept)}. "
                    "Ingest PDFs for richer lessons."
                )

        state.phase = "lesson"
        self._save(state)

        payload = {
            "concept": concept,
            "lesson": lesson_text,
            "chunks": rag_ctx.to_dict()["chunks"],
            "citations": citations,
        }
        return payload

    def get_problem(self, user_id: str) -> dict[str, Any]:
        """Generate and persist one practice problem."""
        uid = validate_user_id(user_id)
        state = self._load(uid)
        diff = DIFFICULTY_SEQUENCE[
            min(state.problem_index, len(DIFFICULTY_SEQUENCE) - 1)
        ]
        user_state = self._build_user_state(state)
        user_state.difficulty = diff

        try:
            problem = self.problems.generate_problem(user_state, state.current_concept)
        except Exception as exc:
            logger.exception("problem generation failed")
            raise ServiceError(f"Problem generation failed: {exc}", 500) from exc

        state.last_problem = {
            "problem_id": problem.problem_id,
            "question": problem.question,
            "expected_answer": problem.expected_answer,
            "concept": problem.concept,
            "difficulty": diff,
            "hint": problem.hint,
        }
        state.phase = "problem"
        self._save(state)

        return {
            "problem": problem.question,
            "difficulty": DIFFICULTY_API.get(diff, "medium"),
            "concept": state.current_concept,
        }

    def submit_answer(self, user_id: str, answer: str) -> dict[str, Any]:
        """Evaluate answer, update memory, return feedback + learning_signal."""
        uid = validate_user_id(user_id)
        trimmed = validate_answer(answer)
        state = self._load(uid)

        if not state.last_problem:
            raise ServiceError(
                "No active problem. Call GET /problem/{user_id} first.", 400
            )

        prob = state.last_problem
        concept = prob["concept"]
        difficulty = prob.get("difficulty", "beginner")

        result = self.evaluator.evaluate_and_update(
            uid,
            state.topic,
            concept,
            trimmed,
            prob["expected_answer"],
            difficulty=difficulty,
            question=prob["question"],
        )

        engine_action = "repeat"
        if result.next_step:
            engine_action = result.next_step.action
        api_action = ACTION_API_MAP.get(engine_action, "repeat")

        state.progression_action = api_action
        state.phase = "feedback"
        self._save(state)

        confidence = result.progress.confidence_score if result.progress else 0.0
        learning_signal = self._learning_signal(
            uid, state.topic, concept, result.mistake_type, result.correct, confidence
        )

        return {
            "is_correct": result.correct,
            "concept": concept,
            "score": result.score,
            "error_type": result.mistake_type,
            "feedback": result.feedback,
            "hint": result.hint,
            "confidence": round(confidence, 4),
            "next_action": api_action,
            "learning_signal": learning_signal,
        }

    def decide_next_step(self, user_id: str) -> dict[str, Any]:
        """Advance problem or concept based on progression rules."""
        uid = validate_user_id(user_id)
        state = self._load(uid)
        concept = state.current_concept

        if state.phase == "feedback":
            state.problem_index += 1
            if state.problem_index < state.problems_per_concept:
                self._save(state)
                return {
                    "next_concept": concept,
                    "action": "repeat",
                    "message": "Continue practicing this concept",
                }
            return self._advance_concept(state)

        if state.phase == "lesson":
            return {
                "next_concept": concept,
                "action": "repeat",
                "message": "Call GET /problem/{user_id} to start practice",
            }

        decision = self.progression.decide_next_step(uid, concept, state.topic)
        return {
            "next_concept": decision.next_concept or concept,
            "action": ACTION_API_MAP.get(decision.action, "repeat"),
            "message": decision.message,
        }

    def get_progress(self, user_id: str) -> dict[str, Any]:
        """Return topic and per-concept confidence."""
        uid = validate_user_id(user_id)
        state = self.sessions.load(uid)
        topic_label = state.topic_label if state else ""
        topic_id = state.topic if state else ""

        if not topic_id:
            rows = self.memory.get_user_progress(uid)
            if not rows:
                return {"topic": "", "topic_id": "", "concepts": []}
            topic_id = rows[0].topic
            topic_label = topic_id

        progress = self.memory.get_user_progress(uid, topic_id)
        concepts_out = [
            {
                "name": p.concept,
                "label": self.concepts.label(p.concept),
                "confidence": round(p.confidence_score, 4),
                "attempts": p.attempts,
            }
            for p in progress
        ]

        if state and state.concepts:
            seen = {c["name"] for c in concepts_out}
            for cid in state.concepts:
                if cid not in seen:
                    concepts_out.append(
                        {
                            "name": cid,
                            "label": self.concepts.label(cid),
                            "confidence": 0.0,
                            "attempts": 0,
                        }
                    )

        result = {
            "topic": topic_label or topic_id,
            "topic_id": topic_id,
            "current_concept": state.current_concept if state else "",
            "concepts": concepts_out,
        }
        if state:
            # Touch last_updated for read endpoints too (recoverability/audit).
            self._save(state)
        return result

    # ----------------------------------------------------------------- helpers
    def _advance_concept(self, state: SessionState) -> dict[str, Any]:
        concept = state.current_concept
        action_raw = state.progression_action or "advance"

        if action_raw in ("advance",):
            state.concept_index += 1
        elif action_raw == "review":
            state.concept_index = max(0, state.concept_index - 1)
        elif action_raw in ("repeat", "reteach"):
            pass
        else:
            state.concept_index += 1

        if state.concept_index >= len(state.concepts):
            state.phase = "done"
            self._save(state)
            return {
                "next_concept": concept,
                "action": "advance",
                "message": "Session complete",
            }

        next_concept = state.concepts[state.concept_index]
        state.problem_index = 0
        state.phase = "lesson"
        state.last_problem = None
        state.progression_action = ""
        state.current_concept = next_concept
        self.memory.set_profile(
            state.user_id, state.topic, current_concept=next_concept
        )
        self._save(state)

        return {
            "next_concept": next_concept,
            "action": action_raw,
            "message": f"Moving to {self.concepts.label(next_concept)}",
        }

    def _learning_signal(
        self,
        user_id: str,
        topic: str,
        concept: str,
        error_type: str,
        is_correct: bool,
        confidence: float,
    ) -> dict[str, bool]:
        """
        Derive tutoring signals for the client.

        - weak_concept: confidence below practice threshold
        - retry_recommended: errors that benefit from another attempt or reteach
        """
        weak_ids = {p.concept for p in self.memory.get_weak_areas(user_id, topic)}
        weak_concept = concept in weak_ids or confidence < CONFIDENCE_PRACTICE
        retry_recommended = (not is_correct) or error_type in (
            "conceptual_error",
            "misinterpretation",
            "calculation_error",
            "incomplete_answer",
        )
        if error_type in ("conceptual_error", "misinterpretation"):
            retry_recommended = True
        return {
            "weak_concept": weak_concept,
            "retry_recommended": retry_recommended,
        }


# Singleton used by routes
_session = LearningSession()


def get_session() -> LearningSession:
    """Return shared LearningSession instance."""
    return _session
