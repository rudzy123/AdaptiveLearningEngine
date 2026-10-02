"""RAG retrieval with structured chunks, citations, and lightweight caching."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from pipeline.retrieval import ChunkRetriever, ScoredChunk

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RagChunk:
    """One retrieved passage for lesson assembly."""

    text: str
    source: str
    score: float
    section: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source": self.source,
            "score": self.score,
            "section": self.section,
        }

    def citation(self) -> str:
        """Human-readable citation line."""
        if self.section:
            return f"Source: {self.source} ({self.section})"
        return f"Source: {self.source}"


@dataclass
class RagLessonContext:
    """Structured RAG output for lesson generation."""

    concept: str
    chunks: list[RagChunk] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunks": [c.to_dict() for c in self.chunks],
            "citations": [c.citation() for c in self.chunks],
        }

    def compose_lesson_text(self, introduction: str = "") -> str:
        """Build lesson body with inline citations."""
        parts = [introduction] if introduction else []
        for i, chunk in enumerate(self.chunks, 1):
            parts.append(f"\n{chunk.text}\n\n_{chunk.citation()}_")
        return "\n".join(parts).strip() if parts else introduction


class RagService:
    """
    Wraps ChunkRetriever with structured output and LRU cache.

    Cache key: (topic, concept tuple) — invalidates naturally via maxsize.
    """

    def __init__(self, cache_size: int = 64) -> None:
        self._retriever: ChunkRetriever | None = None
        self._loaded = False
        self._cache_size = cache_size
        self._retrieve_cached = lru_cache(maxsize=cache_size)(self._retrieve_uncached)

    def _get_retriever(self) -> ChunkRetriever | None:
        if self._retriever is None:
            self._retriever = ChunkRetriever()
        if not self._loaded:
            try:
                self._retriever.load()
                self._loaded = True
            except FileNotFoundError:
                logger.warning("Chunk DB missing — RAG disabled")
                return None
        return self._retriever

    def retrieve_for_concept(
        self,
        concept: str,
        *,
        topic: str = "math",
        weak_concepts: tuple[str, ...] = (),
    ) -> RagLessonContext:
        """
        Return structured chunks for a concept (cached).

        Args:
            concept: Canonical concept id.
            topic: Domain filter.
            weak_concepts: Additional concepts to boost (hashable tuple for cache).
        """
        key = (topic, concept, weak_concepts)
        return self._retrieve_cached(key)

    def _retrieve_uncached(
        self, key: tuple[str, str, tuple[str, ...]]
    ) -> RagLessonContext:
        topic, concept, weak_concepts = key
        retriever = self._get_retriever()
        if retriever is None:
            return RagLessonContext(concept=concept, chunks=[])

        focus = list(dict.fromkeys([concept, *weak_concepts]))
        try:
            lesson_ctx = retriever.retrieve_for_adaptive_lesson(
                focus,
                weak_concepts=list(weak_concepts),
                topic=topic,
            )
        except Exception as exc:
            logger.exception("RAG retrieval failed: %s", exc)
            return RagLessonContext(concept=concept, chunks=[])

        chunks: list[RagChunk] = []
        seen: set[str] = set()
        for section in lesson_ctx.sections:
            section_label = section.concept.replace("_", " ").title()
            for scored in section.chunks:
                if scored.chunk_id in seen:
                    continue
                seen.add(scored.chunk_id)
                chunks.append(self._to_chunk(scored, section_label))
        return RagLessonContext(concept=concept, chunks=chunks)

    @staticmethod
    def _to_chunk(scored: ScoredChunk, section: str) -> RagChunk:
        text = scored.text.strip()
        if len(text) > 1200:
            text = text[:1200] + "…"
        return RagChunk(
            text=text,
            source=scored.source_filename,
            score=round(float(scored.score), 4),
            section=f"Section {section}",
        )

    def clear_cache(self) -> None:
        """Invalidate retrieval cache (e.g. after re-ingest)."""
        self._retrieve_cached.cache_clear()
