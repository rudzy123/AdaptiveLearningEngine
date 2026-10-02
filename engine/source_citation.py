"""Format PDF chunk references for lesson explanations."""

from __future__ import annotations

import textwrap

from pipeline.retrieval import ScoredChunk


def format_pdf_citation(chunk: ScoredChunk) -> str:
    """
    Human-readable citation for an ingested PDF chunk.

    Example: MIT OpenCourseWare — mit_18_06_linear_algebra_zoom_notes.pdf (part 3)
    """
    institution = chunk.institution or "Open Educational Resource"
    filename = chunk.source_filename
    part = chunk.chunk_index + 1
    title = chunk.title.replace("_", " ").strip() if chunk.title else filename
    return f"{institution} — {filename} (section {part}, «{title}»)"


def excerpt_for_difficulty(text: str, difficulty: str) -> str:
    """Trim chunk text for lesson body while keeping readable paragraphs."""
    text = text.strip()
    limits = {"beginner": 900, "intermediate": 1400, "advanced": 2200}
    limit = limits.get(difficulty, 1200)
    if len(text) <= limit:
        return text
    trimmed = text[:limit]
    last_break = trimmed.rfind("\n\n")
    if last_break > limit // 2:
        trimmed = trimmed[:last_break]
    return trimmed.rstrip() + "\n\n[…excerpt continues in source PDF…]"


def build_sourced_passage(chunk: ScoredChunk, difficulty: str) -> dict:
    """
    Build one explanation block grounded in real PDF material.

    Returns a dict with citation metadata and display body.
    """
    citation = format_pdf_citation(chunk)
    excerpt = excerpt_for_difficulty(chunk.text, difficulty)
    body = textwrap.dedent(
        f"""
        **From course materials** ({citation}):

        > {excerpt.replace(chr(10), chr(10) + '> ')}
        """
    ).strip()
    return {
        "citation": citation,
        "source_file": chunk.source_file,
        "institution": chunk.institution,
        "chunk_id": chunk.chunk_id,
        "chunk_index": chunk.chunk_index,
        "relevance_score": chunk.score,
        "body": body,
        "excerpt": excerpt,
    }
