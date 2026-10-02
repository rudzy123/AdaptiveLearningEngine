"""Decide next learning steps based on memory and concept order."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from config import (
    CONFIDENCE_ACCELERATE,
    CONFIDENCE_MASTERED,
    CONFIDENCE_PRACTICE,
    REPEATED_FAILURE_STREAK,
    RETEACH_FAILURE_THRESHOLD,
    STALE_REVIEW_DAYS,
    STRONG_SCORE_ACCELERATE,
)
from engine.concepts import ConceptRegistry
from engine.memory import MemoryStore, UserProgress
from engine.user_state import DifficultyLevel, LearnerLevel, UserState

logger = logging.getLogger(__name__)

ActionType = Literal[
    "advance",
    "practice_harder",
    "repeat",
    "reteach",
    "review_previous",
]


@dataclass
class EvaluationOutcome:
    """Signals from deep evaluation used to drive progression."""

    concept: str
    is_correct: bool
    score: float
    error_type: str
    combined_layer_score: float = 0.0


@dataclass
class ProgressionDecision:
    """Recommended next step for the learner."""

    action: ActionType
    concept: str
    difficulty: DifficultyLevel
    message: str
    next_concept: str | None = None
    focus_concepts: list[str] | None = None
    accelerated: bool = False
    difficulty_adjusted: bool = False


class ProgressionEngine:
    """
    Closed-loop progression rules:

    - confidence > 0.8  → advance to next concept
    - 0.5–0.8         → harder practice on same concept
    - < 0.5           → repeat with simpler explanation
    - 3+ wrong streak → re-teach with alternative explanation
    """

    def __init__(
        self,
        memory: MemoryStore | None = None,
        concepts: ConceptRegistry | None = None,
    ) -> None:
        self.memory = memory or MemoryStore()
        self.concepts = concepts or ConceptRegistry()

    def build_user_state(self, user_id: str, topic: str) -> UserState:
        """Assemble UserState snapshot for generators."""
        profile = self.memory.ensure_user_topic(user_id, topic)
        progress = self.memory.get_user_progress(user_id, topic)
        weak = [p.concept for p in self.memory.get_weak_areas(user_id, topic)]
        strong = [p.concept for p in self.memory.get_strong_areas(user_id, topic)]
        learned = [p.concept for p in progress if p.attempts > 0]

        current = profile.current_concept or self.concepts.get_first_concept(topic)
        record = self.memory.get_concept_progress(user_id, topic, current)
        difficulty = self.adjust_difficulty(user_id, topic, current)

        focus = weak[:3] if weak else [current]
        needs_reteach = self.memory.needs_reteach(user_id, topic, current)

        confidence_map = {p.concept: p.confidence_score for p in progress}

        return UserState(
            user_id=user_id,
            topic=topic,
            current_level=profile.current_level,
            current_concept=current,
            difficulty=difficulty,
            weak_concepts=weak,
            strong_concepts=strong,
            concepts_learned=learned,
            needs_reteach=needs_reteach,
            focus_concepts=focus,
            concept_confidence=confidence_map,
        )

    def adjust_difficulty(
        self,
        user_id: str,
        topic: str,
        concept: str,
        *,
        error_type: str | None = None,
        force_lower: bool = False,
    ) -> DifficultyLevel:
        """
        Map confidence and recent errors to explanation/problem difficulty.

        Repeated failure or conceptual errors pull difficulty down.
        """
        record = self.memory.get_concept_progress(user_id, topic, concept)
        if not record or record.attempts == 0:
            return "beginner"

        if force_lower or (record.consecutive_wrong >= REPEATED_FAILURE_STREAK):
            return "beginner"

        last_error = error_type or self.memory.get_last_mistake_type(
            user_id, topic, concept
        )
        if last_error in ("conceptual_error", "misinterpretation", "guessing"):
            return "beginner"
        if last_error == "incomplete_answer":
            return "beginner"
        if last_error == "calculation_error":
            if record.confidence_score >= CONFIDENCE_PRACTICE:
                return "intermediate"
            return "beginner"

        if record.confidence_score >= CONFIDENCE_MASTERED:
            return "advanced"
        if record.confidence_score >= CONFIDENCE_PRACTICE:
            return "intermediate"
        return "beginner"

    def _lower_difficulty(self, level: DifficultyLevel) -> DifficultyLevel:
        order: list[DifficultyLevel] = ["beginner", "intermediate", "advanced"]
        idx = order.index(level)
        return order[max(0, idx - 1)]

    def _raise_difficulty(self, level: DifficultyLevel) -> DifficultyLevel:
        order: list[DifficultyLevel] = ["beginner", "intermediate", "advanced"]
        idx = order.index(level)
        return order[min(len(order) - 1, idx + 1)]

    def should_review_previous_concept(self, user_id: str, topic: str) -> bool:
        """
        Suggest review if a prior concept in the sequence is stale or weak.

        Checks concepts before current in the ordered list.
        """
        profile = self.memory.get_profile(user_id, topic)
        if not profile or not profile.current_concept:
            return False

        ordered = self.concepts.get_concepts_for_topic(topic)
        if profile.current_concept not in ordered:
            return False

        idx = ordered.index(profile.current_concept)
        if idx == 0:
            return False

        previous = ordered[idx - 1]
        record = self.memory.get_concept_progress(user_id, topic, previous)
        if not record:
            return True
        if record.confidence_score < CONFIDENCE_PRACTICE:
            return True

        # Stale if not practiced recently (optional time-based review)
        try:
            from datetime import datetime, timezone, timedelta

            last = datetime.fromisoformat(record.last_updated.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - last > timedelta(days=STALE_REVIEW_DAYS):
                return record.confidence_score < CONFIDENCE_MASTERED
        except ValueError:
            pass
        return False

    def decide_from_evaluation(
        self,
        user_id: str,
        topic: str,
        outcome: EvaluationOutcome,
    ) -> ProgressionDecision:
        """
        Choose next step from evaluation result (evaluation → progression bridge).

        Rules:
        - conceptual_error / misinterpretation → re-teach at beginner difficulty
        - repeated failure streak → lower difficulty, repeat or reteach
        - strong score + solid confidence → accelerate (advance earlier)
        - calculation_error → harder practice, not full reteach
        """
        concept = outcome.concept
        record = self.memory.get_concept_progress(user_id, topic, concept)
        confidence = record.confidence_score if record else 0.0
        streak = record.consecutive_wrong if record else 0
        base_difficulty = self.adjust_difficulty(
            user_id, topic, concept, error_type=outcome.error_type
        )

        conceptual_count = self.memory.count_recent_errors_by_type(
            user_id, topic, concept, "conceptual_error", limit=5
        )

        # --- Conceptual errors → immediate re-teach ---
        if outcome.error_type in ("conceptual_error", "misinterpretation"):
            self.memory.set_profile(user_id, topic, current_concept=concept)
            return ProgressionDecision(
                action="reteach",
                concept=concept,
                difficulty="beginner",
                message=(
                    f"A conceptual gap was detected in {self.concepts.label(concept)}. "
                    "Let's re-teach with a simpler explanation from your course materials."
                ),
                focus_concepts=[concept],
                difficulty_adjusted=True,
            )

        if conceptual_count >= 2 and not outcome.is_correct:
            return ProgressionDecision(
                action="reteach",
                concept=concept,
                difficulty="beginner",
                message=(
                    f"Repeated conceptual errors on {self.concepts.label(concept)}. "
                    "Switching to an alternative teaching approach."
                ),
                focus_concepts=[concept],
                difficulty_adjusted=True,
            )

        # --- Repeated failure → lower difficulty ---
        if streak >= REPEATED_FAILURE_STREAK or self.memory.needs_reteach(
            user_id, topic, concept
        ):
            lowered: DifficultyLevel = "beginner"
            return ProgressionDecision(
                action="reteach" if streak >= RETEACH_FAILURE_THRESHOLD else "repeat",
                concept=concept,
                difficulty=lowered,
                message=(
                    f"Several attempts missed on {self.concepts.label(concept)}. "
                    f"Dropping to {lowered} difficulty for more support."
                ),
                focus_concepts=[concept],
                difficulty_adjusted=True,
            )

        if outcome.error_type in ("incomplete_answer", "guessing"):
            return ProgressionDecision(
                action="repeat",
                concept=concept,
                difficulty=self._lower_difficulty(base_difficulty),
                message="Try a more complete answer with your reasoning steps shown.",
                focus_concepts=[concept],
                difficulty_adjusted=True,
            )

        if outcome.error_type == "calculation_error":
            return ProgressionDecision(
                action="practice_harder",
                concept=concept,
                difficulty=base_difficulty,
                message=(
                    f"Your approach on {self.concepts.label(concept)} looks reasonable — "
                    "practice more problems and watch arithmetic carefully."
                ),
                focus_concepts=[concept],
            )

        # --- Strong performance → accelerate progression ---
        strong_eval = outcome.is_correct and outcome.score >= STRONG_SCORE_ACCELERATE
        can_accelerate = confidence >= CONFIDENCE_ACCELERATE or (
            strong_eval and outcome.score >= 1.0
        )

        if can_accelerate and (confidence >= CONFIDENCE_MASTERED or outcome.score >= 1.0):
            nxt = self.concepts.get_next_concept(topic, concept)
            if nxt:
                self.memory.set_profile(user_id, topic, current_concept=nxt)
                raised = self._raise_difficulty(base_difficulty)
                return ProgressionDecision(
                    action="advance",
                    concept=nxt,
                    difficulty=raised if outcome.score >= 1.0 else "beginner",
                    next_concept=nxt,
                    message=(
                        f"Excellent work on {self.concepts.label(concept)}! "
                        f"Accelerating to {self.concepts.label(nxt)}."
                    ),
                    focus_concepts=[nxt],
                    accelerated=True,
                )
            return ProgressionDecision(
                action="advance",
                concept=concept,
                difficulty="advanced",
                message="Strong performance — try advanced challenges on this topic.",
                focus_concepts=[concept],
                accelerated=True,
            )

        if strong_eval and confidence >= CONFIDENCE_PRACTICE:
            return ProgressionDecision(
                action="practice_harder",
                concept=concept,
                difficulty=self._raise_difficulty(base_difficulty),
                message=(
                    f"Good answer on {self.concepts.label(concept)}. "
                    "Stepping up problem difficulty."
                ),
                focus_concepts=[concept],
                accelerated=True,
            )

        # Fall back to confidence-based rules
        return self.decide_next_step(user_id, concept, topic)

    def decide_next_step(
        self, user_id: str, current_concept: str, topic: str | None = None
    ) -> ProgressionDecision:
        """
        Determine what the learner should do next for a concept.

        Uses confidence thresholds and failure streaks from memory.
        """
        topic = topic or self._infer_topic(user_id)
        record = self.memory.get_concept_progress(user_id, topic, current_concept)
        confidence = record.confidence_score if record else 0.0
        difficulty = self.adjust_difficulty(user_id, topic, current_concept)

        if self.memory.needs_reteach(user_id, topic, current_concept):
            return ProgressionDecision(
                action="reteach",
                concept=current_concept,
                difficulty="beginner",
                message=(
                    f"Let's revisit {self.concepts.label(current_concept)} "
                    "with a different explanation."
                ),
                focus_concepts=[current_concept],
            )

        if self.should_review_previous_concept(user_id, topic):
            ordered = self.concepts.get_concepts_for_topic(topic)
            idx = ordered.index(current_concept) if current_concept in ordered else 0
            prev = ordered[idx - 1] if idx > 0 else current_concept
            return ProgressionDecision(
                action="review_previous",
                concept=prev,
                difficulty="intermediate",
                message=f"Quick review of {self.concepts.label(prev)} before continuing.",
                focus_concepts=[prev, current_concept],
            )

        if confidence >= CONFIDENCE_MASTERED:
            nxt = self.concepts.get_next_concept(topic, current_concept)
            if nxt:
                self.memory.set_profile(user_id, topic, current_concept=nxt)
                return ProgressionDecision(
                    action="advance",
                    concept=nxt,
                    difficulty="beginner",
                    next_concept=nxt,
                    message=f"Great work! Moving on to {self.concepts.label(nxt)}.",
                    focus_concepts=[nxt],
                )
            return ProgressionDecision(
                action="advance",
                concept=current_concept,
                difficulty="advanced",
                message="You've mastered this topic sequence. Try advanced problems!",
                focus_concepts=[current_concept],
            )

        if confidence >= CONFIDENCE_PRACTICE:
            return ProgressionDecision(
                action="practice_harder",
                concept=current_concept,
                difficulty="intermediate" if difficulty == "beginner" else "advanced",
                message=(
                    f"Solid progress on {self.concepts.label(current_concept)}. "
                    "Trying harder problems."
                ),
                focus_concepts=[current_concept],
            )

        return ProgressionDecision(
            action="repeat",
            concept=current_concept,
            difficulty="beginner",
            message=(
                f"Let's reinforce {self.concepts.label(current_concept)} "
                "with a simpler explanation."
            ),
            focus_concepts=[current_concept],
        )

    def update_level_from_progress(self, user_id: str, topic: str) -> LearnerLevel:
        """Promote learner level when most concepts are strong."""
        progress = self.memory.get_user_progress(user_id, topic)
        if not progress:
            return "beginner"
        strong_ratio = sum(
            1 for p in progress if p.confidence_score >= CONFIDENCE_MASTERED
        ) / max(len(progress), 1)
        if strong_ratio >= 0.7:
            level: LearnerLevel = "advanced"
        elif strong_ratio >= 0.4:
            level = "intermediate"
        else:
            level = "beginner"
        self.memory.set_profile(user_id, topic, current_level=level)
        return level

    def _infer_topic(self, user_id: str) -> str:
        progress = self.memory.get_user_progress(user_id)
        if progress:
            return progress[0].topic
        return "math"
