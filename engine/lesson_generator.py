"""Generate PDF-grounded lessons with weak-area prioritization and source citations."""

from __future__ import annotations

import logging
import textwrap
from dataclasses import dataclass, field

from config import (
    LESSON_CHUNKS_PER_CONCEPT,
    LESSON_CHUNKS_PER_WEAK_CONCEPT,
    LESSON_MAX_CHUNKS,
)
from engine.concepts import ConceptRegistry
from engine.source_citation import build_sourced_passage
from engine.user_state import UserState
from pipeline.retrieval import ChunkRetriever, LessonContext, ScoredChunk

logger = logging.getLogger(__name__)

DIFFICULTY_INTROS = {
    "beginner": "We'll build up from the source readings in small, clear steps.",
    "intermediate": "We'll connect ideas using excerpts from your course PDFs.",
    "advanced": "We'll work from primary materials with fuller technical detail.",
}

RETEACH_NOTE = (
    "\n\n**Alternative approach:** The excerpts below highlight a second path "
    "through the same source material — read them in order.\n"
)


@dataclass
class LessonSection:
    """One concept section with PDF-grounded passages."""

    heading: str
    concept: str
    is_weak_focus: bool
    passages: list[dict] = field(default_factory=list)
    body: str = ""
    sources: list[str] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)


@dataclass
class GeneratedLesson:
    """Lesson built entirely from retrieved PDF chunks when available."""

    title: str
    topic: str
    concept: str
    difficulty: str
    introduction: str
    sections: list[LessonSection] = field(default_factory=list)
    source_context: str = ""
    sources: list[dict] = field(default_factory=list)
    focus_concepts: list[str] = field(default_factory=list)
    retrieval_metadata: dict = field(default_factory=dict)
    user_state_summary: dict = field(default_factory=dict)
    has_pdf_content: bool = False

    def render(self) -> str:
        """Plain-text lesson with explicit material citations."""
        lines = [
            f"# {self.title}",
            f"Topic: {self.topic} | Level: {self.difficulty}",
            "",
            self.introduction,
            "",
        ]
        if not self.has_pdf_content:
            lines.append(
                "_No PDF chunks retrieved. Run ingest_pdfs.py and tag_chunks.py._\n"
            )

        for section in self.sections:
            weak_tag = " [focus: weak area]" if section.is_weak_focus else ""
            lines.append(f"## {section.heading}{weak_tag}")
            lines.append(section.body)
            lines.append("")
            if section.sources:
                lines.append("**Referenced PDFs:**")
                for src in section.sources:
                    lines.append(f"  • {src}")
                lines.append("")

        if self.sources:
            lines.append("---")
            lines.append("## All source documents")
            for src in self.sources:
                lines.append(
                    f"  • {src.get('institution', 'OER')}: {src.get('filename', '')}"
                )
        return "\n".join(lines)


class LessonGenerator:
    """
    Builds lessons by retrieving tagged chunks from ingested PDFs.

    - Weak concepts are retrieved first with extra chunk budget
    - Explanations quote real excerpts with PDF citations
    - No external API; content comes from learning_chunks.db
    """

    def __init__(
        self,
        retriever: ChunkRetriever | None = None,
        concepts: ConceptRegistry | None = None,
    ) -> None:
        self.concepts = concepts or ConceptRegistry()
        self._retriever = retriever
        self._retriever_loaded = False

    def _get_retriever(self) -> ChunkRetriever:
        if self._retriever is None:
            self._retriever = ChunkRetriever()
        if not self._retriever_loaded:
            self._retriever.load()
            self._retriever_loaded = True
        return self._retriever

    def generate_lesson(self, user_state: UserState) -> GeneratedLesson:
        """
        Create a lesson from PDF retrieval, prioritizing weak areas.

        Pipeline:
        1. Build concept list (weak → focus → current)
        2. retrieve_for_adaptive_lesson() from SQLite chunk index
        3. Assemble cited passages per concept
        """
        ordered_concepts = self._build_concept_priority(user_state)
        weak_set = {
            self.concepts.normalize_concept(c) for c in user_state.weak_concepts
        }
        primary = ordered_concepts[0] if ordered_concepts else "general"

        retriever = self._get_retriever()
        topic_filter = self._topic_domain(user_state.topic)

        logger.info(
            "Retrieving PDF chunks: topic=%s concepts=%s weak=%s",
            topic_filter,
            ordered_concepts,
            list(weak_set),
        )

        lesson_ctx = retriever.retrieve_for_adaptive_lesson(
            concepts=ordered_concepts,
            weak_concepts=list(weak_set),
            concept_weights=user_state.concept_confidence,
            topic=topic_filter,
            max_chunks=LESSON_MAX_CHUNKS,
            chunks_per_concept=LESSON_CHUNKS_PER_CONCEPT,
            chunks_per_weak=LESSON_CHUNKS_PER_WEAK_CONCEPT,
            diversify_sources=True,
        )

        intro = self._build_intro(user_state, primary, lesson_ctx)
        if user_state.needs_reteach:
            intro += RETEACH_NOTE

        sections = self._build_sections(
            lesson_ctx, user_state.difficulty, weak_set
        )
        sources_index = self._build_sources_index(lesson_ctx.all_chunks)
        has_content = any(s.passages for s in sections)

        return GeneratedLesson(
            title=self._lesson_title(primary, user_state, has_content),
            topic=user_state.topic,
            concept=primary,
            difficulty=user_state.difficulty,
            introduction=intro,
            sections=sections,
            source_context=lesson_ctx.to_prompt_context(max_chars=4000),
            sources=sources_index,
            focus_concepts=ordered_concepts,
            retrieval_metadata=lesson_ctx.metadata,
            has_pdf_content=has_content,
            user_state_summary={
                "user_id": user_state.user_id,
                "weak": user_state.weak_concepts,
                "strong": user_state.strong_concepts,
                "level": user_state.current_level,
                "retrieved_chunks": len(lesson_ctx.all_chunks),
            },
        )

    def _build_concept_priority(self, user_state: UserState) -> list[str]:
        """Order concepts: weakest first, then focus/current, deduplicated."""
        seen: set[str] = set()
        ordered: list[str] = []

        def add(concept: str) -> None:
            c = self.concepts.normalize_concept(concept)
            if c and c not in seen:
                seen.add(c)
                ordered.append(c)

        weak_sorted = sorted(
            user_state.weak_concepts,
            key=lambda c: user_state.concept_confidence.get(c, 0.0),
        )
        for c in weak_sorted:
            add(c)
        for c in user_state.focus_concepts:
            add(c)
        if user_state.current_concept:
            add(user_state.current_concept)

        if not ordered:
            ordered.append(self.concepts.get_first_concept(user_state.topic))
        return ordered

    def _lesson_title(
        self, primary: str, user_state: UserState, has_pdf: bool
    ) -> str:
        label = self.concepts.label(primary)
        suffix = " (from course PDFs)" if has_pdf else ""
        if primary in user_state.weak_concepts:
            return f"Reinforcing {label}{suffix}"
        return f"{label} — {user_state.difficulty.title()} Lesson{suffix}"

    def _build_intro(
        self, user_state: UserState, primary: str, ctx: LessonContext
    ) -> str:
        label = self.concepts.label(primary)
        level_note = DIFFICULTY_INTROS.get(user_state.difficulty, "")
        pdf_note = ""
        source_count = len(ctx.metadata.get("sources", []))
        if source_count:
            pdf_note = (
                f"\n\nThis lesson pulls **{len(ctx.all_chunks)} excerpts** from "
                f"**{source_count} ingested PDF(s)** in your library."
            )
        weak_note = ""
        if user_state.weak_concepts:
            labels = [
                self.concepts.label(c) for c in user_state.weak_concepts[:3]
            ]
            weak_note = (
                f"\n\n**Priority focus** (weak areas): {', '.join(labels)}. "
                "More material is included for those topics."
            )
        return textwrap.dedent(
            f"""
            Welcome back! Today's lesson centers on **{label}**.
            {level_note}{pdf_note}{weak_note}

            Explanations below quote your open-course PDF readings where available.
            """
        ).strip()

    def _build_sections(
        self,
        ctx: LessonContext,
        difficulty: str,
        weak_concepts: set[str],
    ) -> list[LessonSection]:
        sections: list[LessonSection] = []

        for lesson_section in ctx.sections:
            concept = lesson_section.concept
            passages = [
                build_sourced_passage(chunk, difficulty)
                for chunk in lesson_section.chunks
            ]
            body_parts = [p["body"] for p in passages]
            citations = [p["citation"] for p in passages]

            if not body_parts:
                body = (
                    "_No matching PDF excerpts for this concept. "
                    "Try running download_materials.py and tag_chunks.py._"
                )
            else:
                summary = (
                    f"The following passages are taken directly from your "
                    f"ingested course materials on "
                    f"**{concept.replace('_', ' ')}**:\n\n"
                )
                body = summary + "\n\n".join(body_parts)

            sections.append(
                LessonSection(
                    heading=self.concepts.label(concept),
                    concept=concept,
                    is_weak_focus=concept in weak_concepts,
                    passages=passages,
                    body=body,
                    sources=citations,
                    chunk_ids=[p["chunk_id"] for p in passages],
                )
            )

        if not sections:
            sections.append(
                LessonSection(
                    heading="Overview",
                    concept="general",
                    is_weak_focus=False,
                    body=(
                        "No PDF content matched this lesson. "
                        "Ensure ingest_pdfs.py and tag_chunks.py have been run."
                    ),
                )
            )
        return sections

    @staticmethod
    def _build_sources_index(chunks: list[ScoredChunk]) -> list[dict]:
        by_file: dict[str, dict] = {}
        for chunk in chunks:
            if chunk.source_file not in by_file:
                by_file[chunk.source_file] = {
                    "source_file": chunk.source_file,
                    "filename": chunk.source_filename,
                    "institution": chunk.institution,
                    "title": chunk.title,
                    "chunk_ids": [],
                }
            by_file[chunk.source_file]["chunk_ids"].append(chunk.chunk_id)
        return list(by_file.values())

    def _topic_domain(self, topic: str) -> str | None:
        t = topic.lower()
        if t in ("math", "physics", "cs", "problems"):
            return t
        if "algebra" in t or "linear" in t:
            return "math"
        if "algorithm" in t or "cs" in t:
            return "cs"
        if "physic" in t or "mechanic" in t or "thermo" in t:
            return "physics"
        return None
