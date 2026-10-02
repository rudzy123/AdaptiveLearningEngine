"""Pydantic request/response models for the REST API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LearnerLevel = Literal["beginner", "intermediate", "advanced"]
PanelPhase = Literal[
    "setup", "lesson", "problem", "feedback", "concept_summary", "done"
]


class StartTopicRequest(BaseModel):
    user_id: str = "default"
    topic: str = "math"
    level: LearnerLevel = "beginner"
    problems_per_concept: int = Field(default=3, ge=1, le=10)
    max_concepts: int = Field(default=8, ge=1, le=20)


class ConceptProgressItem(BaseModel):
    concept_id: str
    label: str
    confidence: float
    attempts: int
    correct: int
    is_current: bool = False
    is_weak: bool = False


class ProblemResponse(BaseModel):
    problem_id: str
    concept: str
    question: str
    difficulty: str
    hint: str = ""
    index: int
    total: int


class FeedbackResponse(BaseModel):
    correct: bool
    score: float
    mistake_type: str
    feedback: str
    hint: str
    confidence: float
    confidence_delta: float
    progression_action: str
    progression_message: str


class LessonResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    concept_id: str
    concept_label: str
    title: str
    topic: str
    difficulty: str
    explanation: str
    example: str
    has_pdf: bool
    sources: list[str] = Field(default_factory=list)


class SessionSnapshot(BaseModel):
    session_id: str
    phase: PanelPhase
    topic: str
    user_id: str
    level: str
    current_concept_id: str
    current_concept_label: str
    concept_index: int
    total_concepts: int
    problem_index: int
    problems_per_concept: int
    problems_correct: int
    rag_available: bool
    progression_action: str = ""
    concepts: list[ConceptProgressItem]
    lesson: LessonResponse | None = None
    problem: ProblemResponse | None = None
    feedback: FeedbackResponse | None = None
    error: str | None = None


class SubmitAnswerRequest(BaseModel):
    session_id: str
    answer: str


class SessionIdRequest(BaseModel):
    session_id: str
