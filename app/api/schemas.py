"""Pydantic request/response models (payload inside success envelope)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TopicRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    topic: str = Field(..., min_length=1)
    level: str = Field(default="beginner")


class UserIdBody(BaseModel):
    user_id: str = Field(..., min_length=1)


class AnswerRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)


class StartTopicData(BaseModel):
    message: str
    current_concept: str
    topic: str | None = None
    topic_label: str | None = None


class LessonData(BaseModel):
    concept: str
    lesson: str
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)


class ProblemData(BaseModel):
    problem: str
    difficulty: str
    concept: str


class LearningSignal(BaseModel):
    weak_concept: bool
    retry_recommended: bool


class EvaluationData(BaseModel):
    is_correct: bool
    score: float
    error_type: str
    feedback: str
    hint: str
    confidence: float
    next_action: str
    learning_signal: LearningSignal


class NextStepData(BaseModel):
    next_concept: str
    action: str
    message: str | None = None


class ConceptProgressItem(BaseModel):
    name: str
    confidence: float
    label: str | None = None
    attempts: int | None = None


class ProgressData(BaseModel):
    topic: str
    concepts: list[ConceptProgressItem]
    topic_id: str | None = None
    current_concept: str | None = None
