"""Evaluate learner answers — delegates to deep evaluation engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from engine.memory import MemoryStore, UserProgress
from engine.progression import ProgressionDecision, ProgressionEngine
from generation.evaluation import DeepEvaluator, EvaluationResult as DeepResult

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Outcome of checking one learner answer (compatible with learn_cli)."""

    correct: bool
    concept: str
    mistake_type: str
    feedback: str
    progress: UserProgress | None = None
    next_step: ProgressionDecision | None = None
    score: float = 0.0
    hint: str = ""
    confidence_adjustment: float = 0.0
    hints: list[str] | None = None


class AnswerEvaluator:
    """
    Closed-loop evaluator using the multi-layer generation/evaluation engine.

    Evaluation outcomes flow into ProgressionEngine.decide_from_evaluation().
    """

    def __init__(
        self,
        memory: MemoryStore | None = None,
        progression: ProgressionEngine | None = None,
    ) -> None:
        self.memory = memory or MemoryStore()
        self.progression = progression or ProgressionEngine(self.memory)
        self._deep = DeepEvaluator(self.memory, self.progression)

    def evaluate_and_update(
        self,
        user_id: str,
        topic: str,
        concept: str,
        user_answer: str,
        expected_answer: str,
        *,
        difficulty: str = "beginner",
        question: str = "",
        hint_level: int = 1,
    ) -> EvaluationResult:
        """Deep evaluation + memory update + evaluation-driven progression."""
        deep: DeepResult = self._deep.evaluate(
            user_answer=user_answer,
            correct_answer=expected_answer,
            concept=concept,
            difficulty_level=difficulty,
            user_id=user_id,
            topic=topic,
            question=question,
            hint_level=hint_level,
            update_memory=True,
        )

        progress = self.memory.get_concept_progress(user_id, topic, concept)

        if deep.progression_decision:
            next_step = deep.progression_decision
        else:
            next_step = self.progression.decide_next_step(user_id, concept, topic)

        return EvaluationResult(
            correct=deep.is_correct,
            concept=concept,
            mistake_type=deep.error_type,
            feedback=deep.feedback,
            progress=progress,
            next_step=next_step,
            score=deep.score,
            hint=deep.hint,
            confidence_adjustment=deep.confidence_adjustment,
            hints=deep.hints,
        )
