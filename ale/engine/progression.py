"""Next-step policy: a pure function from learner state to one of four actions.

Rules, evaluated in priority order (the first match wins):

1. 3+ consecutive failures                 -> reteach (easier level)
2. conceptual_error or misinterpretation   -> reteach (easier level)
3. calculation_error                       -> repeat (fresh problem, same level; no reteach)
4. last answer failed                      -> repeat (a failed answer never advances or raises difficulty)
5. confidence >= 0.8                       -> advance
6. 0.5 <= confidence < 0.8                 -> practice_harder
7. confidence < 0.5                        -> repeat
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from ale.engine.config import (
    ADVANCE_CONFIDENCE,
    FAILURE_STREAK_RETEACH,
    MAX_DIFFICULTY,
    MIN_DIFFICULTY,
    PRACTICE_CONFIDENCE,
)

ACTIONS = ("advance", "practice_harder", "repeat", "reteach")


@dataclass(frozen=True)
class StepInput:
    concept: str
    difficulty: int
    confidence: float
    error_type: str  # 'none' | conceptual_error | calculation_error | misinterpretation | incomplete
    passed: bool
    consecutive_failures: int
    next_concept: str | None  # next concept in the topic, or None if this is the last


@dataclass(frozen=True)
class Decision:
    action: str
    rule: str
    reason: str
    next_concept: str | None
    difficulty: int
    lesson_level: str  # 'standard' | 'easy'
    reteach: bool
    topic_complete: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def decide(s: StepInput) -> Decision:
    easier = max(MIN_DIFFICULTY, s.difficulty - 1)
    harder = min(MAX_DIFFICULTY, s.difficulty + 1)

    def d(action, rule, reason, *, concept=None, difficulty=None, level="standard", reteach=False, complete=False):
        return Decision(
            action=action, rule=rule, reason=reason,
            next_concept=concept if concept is not None else s.concept,
            difficulty=difficulty if difficulty is not None else s.difficulty,
            lesson_level=level, reteach=reteach, topic_complete=complete,
        )

    if s.consecutive_failures >= FAILURE_STREAK_RETEACH:
        return d("reteach", "failure_streak",
                 f"{s.consecutive_failures} consecutive failures: reteach at an easier level",
                 difficulty=easier, level="easy", reteach=True)
    if s.error_type in ("conceptual_error", "misinterpretation"):
        return d("reteach", s.error_type,
                 f"{s.error_type.replace('_', ' ')}: reteach at an easier level",
                 difficulty=easier, level="easy", reteach=True)
    if s.error_type == "calculation_error":
        return d("repeat", "calculation_error",
                 "calculation error: more practice at the same level, no full reteach")
    if not s.passed:
        return d("repeat", "failed_attempt",
                 f"answer not yet correct ({s.error_type.replace('_', ' ')}): try a fresh problem at this level")
    if s.confidence >= ADVANCE_CONFIDENCE:
        if s.next_concept is None:
            return d("advance", "confidence_high",
                     f"confidence {s.confidence:.2f} >= {ADVANCE_CONFIDENCE}: topic complete",
                     concept=s.concept, complete=True)
        return d("advance", "confidence_high",
                 f"confidence {s.confidence:.2f} >= {ADVANCE_CONFIDENCE}: advance to the next concept",
                 concept=s.next_concept, difficulty=MIN_DIFFICULTY)
    if s.confidence >= PRACTICE_CONFIDENCE:
        return d("practice_harder", "confidence_mid",
                 f"confidence {s.confidence:.2f} is between {PRACTICE_CONFIDENCE} and {ADVANCE_CONFIDENCE}: "
                 "practice with a harder problem",
                 difficulty=harder)
    return d("repeat", "confidence_low",
             f"confidence {s.confidence:.2f} < {PRACTICE_CONFIDENCE}: repeat at this level")
