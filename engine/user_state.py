"""User state snapshot passed to lesson and problem generators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

DifficultyLevel = Literal["beginner", "intermediate", "advanced"]
LearnerLevel = Literal["beginner", "intermediate", "advanced"]


@dataclass
class UserState:
    """
    Runtime view of a learner for adaptive generation.

    Built from MemoryStore + ProgressionEngine before each lesson/problem.
    """

    user_id: str
    topic: str
    current_level: LearnerLevel = "beginner"
    current_concept: str = ""
    difficulty: DifficultyLevel = "beginner"
    weak_concepts: list[str] = field(default_factory=list)
    strong_concepts: list[str] = field(default_factory=list)
    concepts_learned: list[str] = field(default_factory=list)
    needs_reteach: bool = False
    focus_concepts: list[str] = field(default_factory=list)
    concept_confidence: dict[str, float] = field(default_factory=dict)

    def primary_focus(self) -> str:
        """Concept to prioritize for the next activity."""
        if self.focus_concepts:
            return self.focus_concepts[0]
        if self.current_concept:
            return self.current_concept
        if self.weak_concepts:
            return self.weak_concepts[0]
        return ""
