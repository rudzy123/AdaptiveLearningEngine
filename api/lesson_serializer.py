"""Convert GeneratedLesson to structured API payloads."""

from __future__ import annotations

from engine.concepts import ConceptRegistry
from engine.lesson_generator import GeneratedLesson


def lesson_to_api(
    lesson: GeneratedLesson, concepts: ConceptRegistry | None = None
) -> dict:
    """Structured lesson for the web UI (title, explanation, example)."""
    registry = concepts or ConceptRegistry()
    explanation = lesson.introduction.strip()
    example = ""
    sources: list[str] = []

    for section in lesson.sections:
        if section.body and len(explanation) < 80:
            explanation = section.body.strip()[:2000]
        if section.passages and not example:
            first = section.passages[0]
            example = (first.get("excerpt") or first.get("text") or "")[:800]
        sources.extend(section.sources)

    if not example and lesson.sections:
        example = (lesson.sections[0].body or "")[:800]
    if not example:
        example = (
            f"Practice applying {registry.label(lesson.concept)} "
            f"at the {lesson.difficulty} level using the concepts above."
        )

    return {
        "concept_id": lesson.concept,
        "concept_label": registry.label(lesson.concept),
        "title": lesson.title,
        "topic": lesson.topic,
        "difficulty": lesson.difficulty,
        "explanation": explanation,
        "example": example.strip(),
        "has_pdf": lesson.has_pdf_content,
        "sources": sources[:6],
        "markdown": lesson.render(),
    }
