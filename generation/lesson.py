"""Lesson generation with RAG-backed explanations."""

from __future__ import annotations

from engine.lesson_generator import GeneratedLesson, LessonGenerator, LessonSection

__all__ = ["LessonGenerator", "GeneratedLesson", "LessonSection", "generate_lesson"]


def generate_lesson(user_state) -> GeneratedLesson:
    """Generate an adaptive lesson for the given user state."""
    return LessonGenerator().generate_lesson(user_state)
