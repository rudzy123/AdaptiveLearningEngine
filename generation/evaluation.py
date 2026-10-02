"""Deep multi-layer answer evaluation for the Adaptive Learning Engine."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from config import CONFIDENCE_DELTA, EVAL_CORRECT_THRESHOLD
from engine.memory import MemoryStore
from engine.progression import EvaluationOutcome, ProgressionDecision, ProgressionEngine
from generation.error_detection import ErrorAnalysis, classify_error
from generation.evaluation_store import EvaluationStore
from generation.feedback import generate_feedback
from generation.hints import all_hints, generate_hints
from generation.patterns import MistakePatternTracker
from generation.scoring import LayerScores, combine_layers, score_to_bucket

logger = logging.getLogger(__name__)


def compute_confidence_adjustment(error_type: str, score: float) -> float:
    """
    Layer 5: Adjust confidence delta based on error severity and partial credit.

    Conceptual errors penalize more than calculation slips.
    Partial scores soften the penalty.
    """
    base = CONFIDENCE_DELTA.get(error_type, -0.1)
    if error_type == "none":
        return base
    if score >= 0.4:
        base *= 0.5
    if score >= 0.7:
        base *= 0.25
    return round(base, 4)


def evaluate_answer(
    user_answer: str,
    correct_answer: str,
    concept: str,
    difficulty_level: str,
    user_id: str,
    *,
    topic: str = "general",
    question: str = "",
    update_memory: bool = True,
    hint_level: int = 1,
    memory: MemoryStore | None = None,
) -> dict[str, Any]:
    """
    Evaluate a learner answer through five layers (local, no API).

    Layers:
    1. Exact correctness (numeric tolerance)
    2. Partial credit (similarity)
    3. Reasoning alignment (explanation + concept keywords)
    4. Error classification
    5. Confidence adjustment

    Returns dict with is_correct, score, error_type, feedback, hint,
    confidence_adjustment, and metadata for extension/LLM hooks.
    """
    evaluator = DeepEvaluator(memory=memory)
    result = evaluator.evaluate(
        user_answer=user_answer,
        correct_answer=correct_answer,
        concept=concept,
        difficulty_level=difficulty_level,
        user_id=user_id,
        topic=topic,
        question=question,
        hint_level=hint_level,
        update_memory=update_memory,
    )
    return result.to_dict()


class EvaluationResult:
    """Rich evaluation outcome with progression hooks."""

    def __init__(
        self,
        *,
        is_correct: bool,
        score: float,
        error_type: str,
        feedback: str,
        hint: str,
        confidence_adjustment: float,
        concept: str,
        layer_scores: LayerScores,
        error_analysis: ErrorAnalysis,
        hints: list[str],
        progression_action: str | None = None,
        progression_message: str | None = None,
        progression_decision: ProgressionDecision | None = None,
    ) -> None:
        self.is_correct = is_correct
        self.score = score
        self.error_type = error_type
        self.feedback = feedback
        self.hint = hint
        self.confidence_adjustment = confidence_adjustment
        self.concept = concept
        self.layer_scores = layer_scores
        self.error_analysis = error_analysis
        self.hints = hints
        self.progression_action = progression_action
        self.progression_message = progression_message
        self.progression_decision = progression_decision

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_correct": self.is_correct,
            "score": self.score,
            "error_type": self.error_type,
            "feedback": self.feedback,
            "hint": self.hint,
            "confidence_adjustment": self.confidence_adjustment,
            "concept": self.concept,
            "layer_scores": {
                "exact": self.layer_scores.exact,
                "partial": self.layer_scores.partial,
                "reasoning": self.layer_scores.reasoning,
                "combined": self.layer_scores.combined,
            },
            "hints": self.hints,
            "progression_action": self.progression_action,
            "progression_message": self.progression_message,
            "progression_difficulty": (
                self.progression_decision.difficulty
                if self.progression_decision
                else None
            ),
            "accelerated": (
                self.progression_decision.accelerated
                if self.progression_decision
                else False
            ),
        }


class DeepEvaluator:
    """
    Orchestrates scoring, error detection, feedback, hints, logging, and memory.

    Extensible: swap feedback/hints modules or add LLM post-processors later.
    """

    def __init__(
        self,
        memory: MemoryStore | None = None,
        progression: ProgressionEngine | None = None,
        store: EvaluationStore | None = None,
        patterns: MistakePatternTracker | None = None,
    ) -> None:
        self.memory = memory or MemoryStore()
        self.progression = progression or ProgressionEngine(self.memory)
        self.store = store or EvaluationStore()
        self.patterns = patterns or MistakePatternTracker()

    def evaluate(
        self,
        *,
        user_answer: str,
        correct_answer: str,
        concept: str,
        difficulty_level: str,
        user_id: str,
        topic: str = "general",
        question: str = "",
        hint_level: int = 1,
        update_memory: bool = True,
    ) -> EvaluationResult:
        """Run full evaluation pipeline."""
        layer = combine_layers(user_answer, correct_answer, concept)
        bucket = score_to_bucket(layer.combined)
        is_correct = layer.combined >= EVAL_CORRECT_THRESHOLD

        error = classify_error(
            user_answer, correct_answer, concept, layer, is_correct
        )
        confidence_adj = compute_confidence_adjustment(error.error_type, layer.combined)

        feedback = generate_feedback(
            concept=concept,
            user_answer=user_answer,
            correct_answer=correct_answer,
            error=error,
            layer=layer,
            is_correct=is_correct,
            score=bucket,
        )
        hint = generate_hints(concept, error.error_type, level=hint_level)
        hints = all_hints(concept, error.error_type)

        decision: ProgressionDecision | None = None

        if update_memory:
            self._update_memory_and_progression(
                user_id=user_id,
                topic=topic,
                concept=concept,
                is_correct=is_correct,
                score=bucket,
                layer=layer,
                error_type=error.error_type,
                difficulty=difficulty_level,
                user_answer=user_answer,
                correct_answer=correct_answer,
                confidence_adj=confidence_adj,
            )
            outcome = EvaluationOutcome(
                concept=concept,
                is_correct=is_correct,
                score=bucket,
                error_type=error.error_type,
                combined_layer_score=layer.combined,
            )
            decision = self.progression.decide_from_evaluation(
                user_id, topic, outcome
            )
            self._apply_progression_to_profile(user_id, topic, decision)
            feedback = f"{feedback}\n\nNext: {decision.message}"

        self.store.log_evaluation(
            {
                "user_id": user_id,
                "topic": topic,
                "concept": concept,
                "question": question,
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "difficulty_level": difficulty_level,
                "is_correct": is_correct,
                "score": bucket,
                "error_type": error.error_type,
                "feedback": feedback,
                "hint": hint,
                "confidence_adjustment": confidence_adj,
                "layer_scores": {
                    "exact": layer.exact,
                    "partial": layer.partial,
                    "reasoning": layer.reasoning,
                    "combined": layer.combined,
                },
                "hints": hints,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        logger.info(
            "Deep eval: user=%s concept=%s score=%.2f error=%s correct=%s",
            user_id,
            concept,
            bucket,
            error.error_type,
            is_correct,
        )

        return EvaluationResult(
            is_correct=is_correct,
            score=bucket,
            error_type=error.error_type,
            feedback=feedback,
            hint=hint,
            confidence_adjustment=confidence_adj,
            concept=concept,
            layer_scores=layer,
            error_analysis=error,
            hints=hints,
            progression_action=decision.action if decision else None,
            progression_message=decision.message if decision else None,
            progression_decision=decision,
        )

    def _apply_progression_to_profile(
        self, user_id: str, topic: str, decision: ProgressionDecision
    ) -> None:
        target = decision.next_concept or decision.concept
        self.memory.set_profile(
            user_id,
            topic,
            current_concept=target,
        )
        self.progression.update_level_from_progress(user_id, topic)

    def _update_memory_and_progression(
        self,
        *,
        user_id: str,
        topic: str,
        concept: str,
        is_correct: bool,
        score: float,
        layer: LayerScores,
        error_type: str,
        difficulty: str,
        user_answer: str,
        correct_answer: str,
        confidence_adj: float,
    ) -> None:
        """Update memory with partial credit and error-weighted confidence."""
        partial_correct = is_correct or score >= 0.4
        self.memory.update_progress(
            user_id,
            topic,
            concept,
            partial_correct,
            difficulty=difficulty,
            user_answer=user_answer,
            expected_answer=correct_answer,
            mistake_type=error_type if not is_correct else None,
            score=layer.combined,
            confidence_delta=confidence_adj,
        )

