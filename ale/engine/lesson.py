"""Lesson generation: retrieve chunks, then assemble an extractive, cited lesson.

There is no generative model. Every sentence in `body` and `key_points` is copied from a retrieved
chunk; the only authored text is the objective (from the curriculum) and the adaptation note.
That is what makes the lesson grounded: each excerpt carries a citation with source, section,
chunk id and retrieval score.
"""

from __future__ import annotations

from ale.engine.curriculum import Concept
from ale.engine.errors import TutorError
from ale.engine.retrieval import Hit, Retriever
from ale.engine.store import ConceptMemory
from ale.engine.text import sentences, stems

CHUNKS_STANDARD = 3
CHUNKS_EASY = 2
EASY_SENTENCES = 3
GENERATOR = "extractive-template (local, no LLM)"


RELEVANCE_FLOOR = 0.5  # keep chunks scoring at least this fraction of the best hit


def build_query(concept: Concept) -> str:
    """Concept-only query; the title is repeated because query-term frequency weights the BM25 sum."""
    return f"{concept.title} {concept.title} {concept.title} {concept.query}"


def section_preference(level: str, memory: ConceptMemory) -> list[str]:
    """Section-heading keywords to prefer, in priority order, given what the learner needs."""
    if level == "easy":
        return ["intuition", "worked example", "common mistakes", "definition"]
    if memory.last_error_type in ("conceptual_error", "misinterpretation"):
        return ["common mistakes", "intuition"]
    if memory.last_error_type == "calculation_error":
        return ["worked example"]
    return []


def select_hits(hits: list[Hit], k: int, preference: list[str], previous: set[str], rotate: bool) -> tuple[list[Hit], bool]:
    """Pick k relevant hits: fresh chunks first (when rotating), then preferred sections, then score."""
    if not hits:
        return [], False
    floor = hits[0].score * RELEVANCE_FLOOR
    relevant = [h for h in hits if h.score >= floor]

    def rank(h: Hit) -> tuple:
        section = h.chunk.section.lower()
        pref = next((i for i, kw in enumerate(preference) if kw in section), len(preference))
        return (h.chunk.chunk_id in previous if rotate else False, pref, -h.score)

    chosen = sorted(relevant, key=rank)[:k]
    reused = rotate and any(h.chunk.chunk_id in previous for h in chosen)
    return chosen, reused


def _key_points(excerpts: list[str], concept: Concept, n: int = 3) -> list[str]:
    """The most concept-dense sentences among the excerpts actually shown to the learner."""
    wanted = set(stems(concept.query + " " + concept.title))
    scored = []
    for excerpt in excerpts:
        for sent in sentences(excerpt):
            toks = stems(sent)
            if len(toks) < 5:
                continue
            scored.append((len(wanted & set(toks)) / (len(set(toks)) or 1), sent))
    scored.sort(key=lambda x: -x[0])
    out: list[str] = []
    for _, sent in scored:
        if sent not in out:
            out.append(sent)
        if len(out) == n:
            break
    return out


def _adaptation_note(level: str, memory: ConceptMemory, reused: bool) -> str:
    if memory.attempts == 0:
        return "First pass on this concept at the standard level."
    if level == "easy":
        why = memory.last_error_type.replace("_", " ") if memory.last_error_type != "none" else "repeated misses"
        tail = " Few alternative sections exist, so some are reused." if reused else ""
        return (
            f"Reteach at an easier level after {why}: shorter excerpts, intuition and examples first, "
            f"sections different from the previous lesson where available.{tail}"
        )
    if memory.last_error_type in ("conceptual_error", "misinterpretation"):
        return "Standard level. Retrieval emphasises common mistakes because of the last error."
    if memory.last_error_type == "calculation_error":
        return "Standard level. Retrieval emphasises worked examples because of the last error."
    return "Standard level."


def build_lesson(
    retriever: Retriever,
    concept: Concept,
    *,
    level: str,
    difficulty: int,
    memory: ConceptMemory,
    previous_chunk_ids: list[str],
) -> dict:
    query = build_query(concept)
    k = CHUNKS_EASY if level == "easy" else CHUNKS_STANDARD
    candidates = retriever.search(query, k=10)
    chosen, reused = select_hits(
        candidates, k, section_preference(level, memory), set(previous_chunk_ids), rotate=(level == "easy")
    )
    if not chosen:
        raise TutorError(
            f"No source material matched '{concept.title}'. Ingest more text with `python -m ale ingest`.",
            "no_context",
            422,
        )
    hits = sorted(chosen, key=lambda h: h.chunk.chunk_id)  # reading order; scores stay on the citations

    parts = [f"**Objective.** {concept.objective}", ""]
    citations = []
    for n, hit in enumerate(hits, start=1):
        excerpt = hit.chunk.text
        if level == "easy":
            excerpt = " ".join(sentences(excerpt)[:EASY_SENTENCES])
        citations.append(hit.citation(n, excerpt))
        parts.append(f"**{hit.chunk.section}** [{n}]")
        parts.append(f"{excerpt} [{n}]")
        parts.append("")
    return {
        "concept": concept.id,
        "concept_title": concept.title,
        "title": f"{concept.title}" + (" (reteach, easier level)" if level == "easy" else ""),
        "level": level,
        "difficulty": difficulty,
        "objective": concept.objective,
        "body": "\n".join(parts).strip(),
        "key_points": _key_points([c["excerpt"] for c in citations], concept),
        "citations": citations,
        "adaptation_note": _adaptation_note(level, memory, reused),
        "retrieval": {
            "engine": "bm25-local",
            "query": query,
            "chunks_indexed": len(retriever.chunks),
        },
        "generator": GENERATOR,
    }
