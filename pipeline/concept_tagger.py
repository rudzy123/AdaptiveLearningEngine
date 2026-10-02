"""Tag ingested chunks with canonical concept labels."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from config import MAX_CONCEPTS_PER_CHUNK, MIN_CONCEPT_TAG_SCORE
from pipeline.chunk_repository import ChunkRecord
from pipeline.concept_lexicon import CONCEPT_LEXICON, ConceptDefinition, concepts_for_domain
from pipeline.content_analyzer import STOPWORDS, tokenize

@dataclass
class ConceptTag:
    """A concept label attached to a chunk with confidence."""

    concept: str
    score: float
    match_type: str  # phrase | alias | token


@dataclass
class TaggedChunk:
    """Chunk with extracted concept tags."""

    chunk: ChunkRecord
    concepts: list[ConceptTag] = field(default_factory=list)

    @property
    def concept_names(self) -> list[str]:
        return [t.concept for t in self.concepts]


def _count_phrase(text: str, phrase: str) -> int:
    return len(re.findall(re.escape(phrase), text, flags=re.IGNORECASE))


def _count_alias(text: str, alias: str) -> int:
    if " " in alias:
        return _count_phrase(text, alias)
    pattern = re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE)
    return len(pattern.findall(text))


def _score_concept(
    text: str,
    tokens: list[str],
    token_counts: dict[str, int],
    definition: ConceptDefinition,
    chunk_words: int,
) -> ConceptTag | None:
    hits = 0.0
    match_type = "token"

    for phrase in definition.phrases:
        count = _count_phrase(text, phrase)
        if count:
            hits += count * 3.0
            match_type = "phrase"

    for alias in definition.aliases:
        count = _count_alias(text, alias)
        if count:
            hits += count * 2.0
            match_type = "alias" if match_type == "token" else match_type

    canonical_count = token_counts.get(definition.canonical, 0)
    if canonical_count:
        hits += canonical_count * 1.5

    for alias in definition.aliases:
        if " " not in alias:
            canonical_count += token_counts.get(alias.lower(), 0)
    if hits == 0:
        return None

    # Normalize by chunk length (log dampening)
    normalized = hits / math.log(chunk_words + math.e)
    score = min(1.0, normalized / 4.0)

    if score < MIN_CONCEPT_TAG_SCORE:
        return None

    return ConceptTag(concept=definition.canonical, score=round(score, 4), match_type=match_type)


def tag_chunk(chunk: ChunkRecord) -> TaggedChunk:
    """Extract concept tags for a single chunk."""
    text = chunk.text.lower()
    tokens = [t for t in tokenize(chunk.text) if t not in STOPWORDS]
    token_counts: dict[str, int] = {}
    for token in tokens:
        token_counts[token] = token_counts.get(token, 0) + 1

    chunk_words = max(len(tokens), 1)
    domain_entries = concepts_for_domain(chunk.topic)
    domain_canonicals = {e.canonical for e in domain_entries}
    lexicon = domain_entries + [
        c for c in CONCEPT_LEXICON if c.canonical not in domain_canonicals
    ]
    unique_lexicon = lexicon

    tags: list[ConceptTag] = []
    for definition in unique_lexicon:
        tag = _score_concept(text, tokens, token_counts, definition, chunk_words)
        if tag:
            tags.append(tag)

    tags.sort(key=lambda t: t.score, reverse=True)
    return TaggedChunk(chunk=chunk, concepts=tags[:MAX_CONCEPTS_PER_CHUNK])


def tag_chunks(chunks: list[ChunkRecord]) -> list[TaggedChunk]:
    """Tag all chunks in the corpus."""
    return [tag_chunk(chunk) for chunk in chunks]
