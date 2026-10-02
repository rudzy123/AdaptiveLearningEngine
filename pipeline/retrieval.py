"""Retrieve tagged, grouped chunks for adaptive lesson generation."""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from config import (
    LESSON_CHUNKS_PER_CONCEPT,
    LESSON_CHUNKS_PER_WEAK_CONCEPT,
    LESSON_MAX_CHUNKS,
    RETRIEVAL_DEFAULT_TOP_K,
    RETRIEVAL_MIN_SCORE,
    SQLITE_DB_PATH,
    WEAK_CONCEPT_SCORE_BOOST,
)
from pipeline.content_analyzer import STOPWORDS, tokenize
from pipeline.knowledge_index import ChunkWithConcepts, load_tagged_chunks

TOKEN_PATTERN = re.compile(r"[a-z][a-z0-9\-]{2,}")


@dataclass
class ScoredChunk:
    """A chunk ranked for relevance to a lesson query."""

    chunk_id: str
    score: float
    text: str
    source_file: str
    topic: str
    subtopic: str
    title: str
    institution: str = ""
    concepts: list[str] = field(default_factory=list)
    concept_scores: dict[str, float] = field(default_factory=dict)
    group_ids: list[str] = field(default_factory=list)
    chunk_index: int = 0
    word_count: int = 0

    @property
    def source_filename(self) -> str:
        """PDF filename for display citations."""
        return self.source_file.split("/")[-1] if self.source_file else "unknown.pdf"


@dataclass
class LessonSection:
    """Content grouped by concept for one lesson segment."""

    concept: str
    chunks: list[ScoredChunk]
    related_group_ids: list[str] = field(default_factory=list)


@dataclass
class LessonContext:
    """Structured retrieval result for lesson generation."""

    query_concepts: list[str]
    query_text: str
    sections: list[LessonSection]
    all_chunks: list[ScoredChunk]
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "query_concepts": self.query_concepts,
            "query_text": self.query_text,
            "metadata": self.metadata,
            "sections": [
                {
                    "concept": section.concept,
                    "related_group_ids": section.related_group_ids,
                    "chunks": [
                        {
                            "chunk_id": c.chunk_id,
                            "score": c.score,
                            "source_file": c.source_file,
                            "topic": c.topic,
                            "concepts": c.concepts,
                            "text_preview": c.text[:500],
                            "text": c.text,
                        }
                        for c in section.chunks
                    ],
                }
                for section in self.sections
            ],
            "all_chunk_ids": [c.chunk_id for c in self.all_chunks],
        }

    def to_prompt_context(self, max_chars: int = 12000) -> str:
        """Format retrieved chunks as context for an LLM lesson prompt."""
        parts: list[str] = []
        used = 0
        for section in self.sections:
            header = f"\n## Concept: {section.concept.replace('_', ' ').title()}\n"
            if used + len(header) > max_chars:
                break
            parts.append(header)
            used += len(header)
            for chunk in section.chunks:
                inst = chunk.institution or "OER"
                block = (
                    f"\n[{inst}: {chunk.source_filename} | "
                    f"section {chunk.chunk_index + 1} | score={chunk.score:.2f}]\n"
                    f"{chunk.text.strip()}\n"
                )
                if used + len(block) > max_chars:
                    break
                parts.append(block)
                used += len(block)
        return "".join(parts).strip()


class ChunkRetriever:
    """Search and rank chunks by concepts, topic filters, and free-text queries."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or str(SQLITE_DB_PATH)
        self._chunks: list[ChunkWithConcepts] = []
        self._idf: dict[str, float] = {}
        self._tf_by_chunk: dict[str, Counter[str]] = {}
        self._loaded = False

    def load(self) -> None:
        self._chunks = load_tagged_chunks()
        if not self._chunks:
            raise FileNotFoundError(
                "No tagged chunks found. Run tag_chunks.py after ingest_pdfs.py."
            )
        self._build_tfidf_index()
        self._loaded = True

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def _build_tfidf_index(self) -> None:
        doc_freq: Counter[str] = Counter()
        self._tf_by_chunk = {}

        for chunk in self._chunks:
            tokens = [
                t for t in tokenize(chunk.text) if t not in STOPWORDS and len(t) > 2
            ]
            tf = Counter(tokens)
            self._tf_by_chunk[chunk.chunk_id] = tf
            for term in tf:
                doc_freq[term] += 1

        n_docs = max(len(self._chunks), 1)
        self._idf = {
            term: math.log((n_docs + 1) / (freq + 1)) + 1.0
            for term, freq in doc_freq.items()
        }

    def _tfidf_score(self, chunk_id: str, query_terms: list[str]) -> float:
        tf_map = self._tf_by_chunk.get(chunk_id, Counter())
        score = 0.0
        for term in query_terms:
            if term in tf_map:
                score += tf_map[term] * self._idf.get(term, 1.0)
        return score

    @staticmethod
    def _normalize_concepts(concepts: list[str]) -> list[str]:
        normalized = []
        for concept in concepts:
            c = concept.strip().lower().replace(" ", "_").replace("-", "_")
            if c:
                normalized.append(c)
        return list(dict.fromkeys(normalized))

    def _concept_match_score(
        self,
        chunk: ChunkWithConcepts,
        query_concepts: list[str],
        *,
        weak_concepts: set[str] | None = None,
        concept_weights: dict[str, float] | None = None,
    ) -> float:
        if not query_concepts:
            return 0.0
        tag_map = {t.concept: t.score for t in chunk.concepts}
        score = 0.0
        weak = weak_concepts or set()
        weights = concept_weights or {}

        for concept in query_concepts:
            multiplier = 1.0
            if concept in weak:
                # Lower learner confidence → stronger retrieval boost for that concept
                confidence = weights.get(concept, 0.0)
                multiplier = WEAK_CONCEPT_SCORE_BOOST * (1.0 + (1.0 - confidence))
            match = 0.0
            if concept in tag_map:
                match = tag_map[concept] * 2.0
            for tagged, tag_score in tag_map.items():
                if concept in tagged or tagged in concept:
                    match += tag_score
            score += match * multiplier
        return score

    def _rank_chunks(
        self,
        query_concepts: list[str],
        query_text: str = "",
        *,
        topic: str | None = None,
        subtopic: str | None = None,
        top_k: int = RETRIEVAL_DEFAULT_TOP_K,
        require_all_concepts: bool = False,
        weak_concepts: list[str] | None = None,
        concept_weights: dict[str, float] | None = None,
    ) -> list[ScoredChunk]:
        self._ensure_loaded()
        query_concepts = self._normalize_concepts(query_concepts)
        weak_set = set(self._normalize_concepts(weak_concepts or []))
        query_terms = [
            t for t in tokenize(query_text) if t not in STOPWORDS
        ] + query_concepts

        scored: list[ScoredChunk] = []
        for chunk in self._chunks:
            if topic and chunk.topic != topic:
                continue
            if subtopic and chunk.subtopic != subtopic:
                continue

            matched = [c for c in query_concepts if c in {t.concept for t in chunk.concepts}]
            if require_all_concepts and query_concepts:
                if len(matched) < len(query_concepts):
                    continue

            concept_score = self._concept_match_score(
                chunk,
                query_concepts,
                weak_concepts=weak_set,
                concept_weights=concept_weights,
            )
            text_score = self._tfidf_score(chunk.chunk_id, query_terms)
            total = concept_score + text_score

            if total < RETRIEVAL_MIN_SCORE and (query_concepts or query_text):
                continue

            scored.append(
                ScoredChunk(
                    chunk_id=chunk.chunk_id,
                    score=round(total, 4),
                    text=chunk.text,
                    source_file=chunk.source_file,
                    topic=chunk.topic,
                    subtopic=chunk.subtopic,
                    title=chunk.title,
                    institution=chunk.institution,
                    concepts=[t.concept for t in chunk.concepts],
                    concept_scores={t.concept: t.score for t in chunk.concepts},
                    group_ids=chunk.group_ids,
                    chunk_index=chunk.chunk_index,
                    word_count=chunk.word_count,
                )
            )

        scored.sort(key=lambda c: (-c.score, c.source_file, c.chunk_index))
        return scored[:top_k]

    def retrieve(
        self,
        concepts: list[str] | None = None,
        query: str = "",
        *,
        topic: str | None = None,
        subtopic: str | None = None,
        top_k: int = RETRIEVAL_DEFAULT_TOP_K,
        require_all_concepts: bool = False,
        weak_concepts: list[str] | None = None,
        concept_weights: dict[str, float] | None = None,
    ) -> list[ScoredChunk]:
        """Retrieve top-k chunks matching concepts and/or a text query."""
        return self._rank_chunks(
            concepts or [],
            query,
            topic=topic,
            subtopic=subtopic,
            top_k=top_k,
            require_all_concepts=require_all_concepts,
            weak_concepts=weak_concepts,
            concept_weights=concept_weights,
        )

    def retrieve_related(self, chunk_id: str, top_k: int = 6) -> list[ScoredChunk]:
        """Return chunks in the same group(s) or sharing concepts."""
        self._ensure_loaded()
        source = next((c for c in self._chunks if c.chunk_id == chunk_id), None)
        if not source:
            return []

        concepts = [t.concept for t in source.concepts[:4]]
        related = self.retrieve(concepts=concepts, top_k=top_k * 2)
        group_set = set(source.group_ids)
        filtered = [
            c for c in related
            if c.chunk_id != chunk_id
            and (set(c.group_ids) & group_set or set(c.concepts) & set(concepts))
        ]
        return filtered[:top_k]

    def retrieve_for_lesson(
        self,
        concepts: list[str],
        *,
        query: str = "",
        topic: str | None = None,
        subtopic: str | None = None,
        max_chunks: int = 12,
        chunks_per_concept: int = 4,
        diversify_sources: bool = True,
    ) -> LessonContext:
        """
        Build a lesson-ready context: chunks grouped by target concept.

        Uses concept-first retrieval with optional source diversification.
        """
        query_concepts = self._normalize_concepts(concepts)
        sections: list[LessonSection] = []
        seen_ids: set[str] = set()
        all_chunks: list[ScoredChunk] = []

        for concept in query_concepts or ["general"]:
            hits = self.retrieve(
                concepts=[concept] if concept != "general" else [],
                query=query,
                topic=topic,
                subtopic=subtopic,
                top_k=chunks_per_concept * 3,
            )
            selected: list[ScoredChunk] = []
            used_sources: set[str] = set()

            for hit in hits:
                if hit.chunk_id in seen_ids:
                    continue
                if diversify_sources and hit.source_file in used_sources:
                    if len(selected) >= chunks_per_concept // 2:
                        continue
                selected.append(hit)
                seen_ids.add(hit.chunk_id)
                used_sources.add(hit.source_file)
                if len(selected) >= chunks_per_concept:
                    break

            if selected:
                group_ids = list(
                    dict.fromkeys(gid for h in selected for gid in h.group_ids)
                )[:5]
                sections.append(
                    LessonSection(
                        concept=concept,
                        chunks=selected,
                        related_group_ids=group_ids,
                    )
                )
                all_chunks.extend(selected)

        # Fill remaining budget with a blended query
        remaining = max_chunks - len(all_chunks)
        if remaining > 0 and query_concepts:
            extra = self.retrieve(
                concepts=query_concepts,
                query=query,
                topic=topic,
                subtopic=subtopic,
                top_k=remaining + len(seen_ids),
            )
            for hit in extra:
                if hit.chunk_id not in seen_ids and len(all_chunks) < max_chunks:
                    all_chunks.append(hit)
                    seen_ids.add(hit.chunk_id)

        all_chunks.sort(key=lambda c: -c.score)
        return LessonContext(
            query_concepts=query_concepts,
            query_text=query,
            sections=sections,
            all_chunks=all_chunks[:max_chunks],
            metadata={
                "topic": topic,
                "subtopic": subtopic,
                "total_sections": len(sections),
                "total_chunks": len(all_chunks),
            },
        )

    def retrieve_for_adaptive_lesson(
        self,
        concepts: list[str],
        *,
        weak_concepts: list[str] | None = None,
        concept_weights: dict[str, float] | None = None,
        query: str = "",
        topic: str | None = None,
        subtopic: str | None = None,
        max_chunks: int = LESSON_MAX_CHUNKS,
        chunks_per_concept: int = LESSON_CHUNKS_PER_CONCEPT,
        chunks_per_weak: int = LESSON_CHUNKS_PER_WEAK_CONCEPT,
        diversify_sources: bool = True,
    ) -> LessonContext:
        """
        PDF-grounded lesson retrieval with weak-area prioritization.

        - Weak concepts are ordered first and receive more chunk slots
        - Scoring boosts chunks tagged with low-confidence concepts
        - Returns grouped sections ready for cited explanations
        """
        normalized_weak = set(self._normalize_concepts(weak_concepts or []))
        normalized_all = self._normalize_concepts(concepts)

        # Order: weakest concepts first, then remaining lesson concepts
        def weak_sort_key(c: str) -> float:
            return concept_weights.get(c, 0.0) if concept_weights else 0.0

        weak_ordered = sorted(
            [c for c in normalized_all if c in normalized_weak],
            key=weak_sort_key,
        )
        other = [c for c in normalized_all if c not in normalized_weak]
        ordered_concepts = list(dict.fromkeys(weak_ordered + other))
        if not ordered_concepts:
            ordered_concepts = ["general"]

        sections: list[LessonSection] = []
        seen_ids: set[str] = set()
        all_chunks: list[ScoredChunk] = []

        for concept in ordered_concepts:
            is_weak = concept in normalized_weak
            limit = chunks_per_weak if is_weak else chunks_per_concept
            hits = self.retrieve(
                concepts=[concept] if concept != "general" else [],
                query=query,
                topic=topic,
                subtopic=subtopic,
                top_k=limit * 4,
                weak_concepts=list(normalized_weak),
                concept_weights=concept_weights,
            )
            selected: list[ScoredChunk] = []
            used_sources: set[str] = set()

            for hit in hits:
                if hit.chunk_id in seen_ids:
                    continue
                if len(all_chunks) >= max_chunks:
                    break
                if diversify_sources and hit.source_file in used_sources:
                    if len(selected) >= max(1, limit // 2):
                        continue
                selected.append(hit)
                seen_ids.add(hit.chunk_id)
                used_sources.add(hit.source_file)
                if len(selected) >= limit:
                    break

            if selected:
                group_ids = list(
                    dict.fromkeys(gid for h in selected for gid in h.group_ids)
                )[:5]
                sections.append(
                    LessonSection(
                        concept=concept,
                        chunks=selected,
                        related_group_ids=group_ids,
                    )
                )
                all_chunks.extend(selected)

        all_chunks.sort(key=lambda c: -c.score)
        return LessonContext(
            query_concepts=ordered_concepts,
            query_text=query,
            sections=sections,
            all_chunks=all_chunks[:max_chunks],
            metadata={
                "topic": topic,
                "subtopic": subtopic,
                "weak_concepts": list(normalized_weak),
                "prioritized_weak": True,
                "total_sections": len(sections),
                "total_chunks": min(len(all_chunks), max_chunks),
                "sources": list(
                    dict.fromkeys(c.source_file for c in all_chunks if c.source_file)
                ),
            },
        )
