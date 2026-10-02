"""Text chunking with configurable word targets and overlap."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from config import (
    CHUNK_MAX_WORDS,
    CHUNK_MIN_WORDS,
    CHUNK_OVERLAP_WORDS,
    CHUNK_TARGET_WORDS,
)


@dataclass
class TextChunk:
    """A single chunk of document text with metadata."""

    chunk_id: str
    text: str
    word_count: int
    chunk_index: int
    source_file: str
    topic: str
    subtopic: str
    institution: str
    title: str


def normalize_whitespace(text: str) -> str:
    """Collapse excessive whitespace while preserving paragraph breaks."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_into_chunks(
    text: str,
    *,
    source_file: str,
    topic: str,
    subtopic: str = "",
    institution: str = "",
    title: str = "",
) -> list[TextChunk]:
    """Split text into overlapping word-based chunks."""
    text = normalize_whitespace(text)
    if not text:
        return []

    words = text.split()
    if not words:
        return []

    chunks: list[TextChunk] = []
    start = 0
    index = 0

    while start < len(words):
        end = min(start + CHUNK_TARGET_WORDS, len(words))

        # Expand to max if we're close to target and more words remain
        if end - start < CHUNK_MIN_WORDS and end < len(words):
            end = min(start + CHUNK_MAX_WORDS, len(words))

        chunk_words = words[start:end]
        if not chunk_words:
            break

        chunk_text = " ".join(chunk_words)
        chunks.append(
            TextChunk(
                chunk_id=str(uuid.uuid4()),
                text=chunk_text,
                word_count=len(chunk_words),
                chunk_index=index,
                source_file=source_file,
                topic=topic,
                subtopic=subtopic,
                institution=institution,
                title=title,
            )
        )
        index += 1

        if end >= len(words):
            break
        start = max(end - CHUNK_OVERLAP_WORDS, start + 1)

    return chunks
