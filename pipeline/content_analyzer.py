"""Corpus-level text analysis for curriculum building."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from pipeline.chunk_repository import ChunkRecord, SourceDocument

# Common English stopwords (stdlib-only; no NLTK dependency)
STOPWORDS = frozenset(
    """
    a an the and or but if in on at to for of as is are was were be been being
    by with from that this these those it its we you they he she his her their
    our not no nor so than then there when where which who what how all any each
    few more most other some such only own same into over after before between
    through during above below up down out off about can will just don should
    now also very one two may use used using lecture chapter page figure mit
    ocw course notes pdf fall spring summer www http https edu
    """.split()
)

# Boost terms that signal educational concepts in STEM corpora
CONCEPT_HINTS: dict[str, frozenset[str]] = {
    "math": frozenset(
        "matrix vector linear eigenvalue determinant transpose "
        "elimination subspace rank orthogonal decomposition".split()
    ),
    "physics": frozenset(
        "force energy momentum velocity acceleration newton entropy "
        "thermodynamic equilibrium temperature pressure heat work".split()
    ),
    "cs": frozenset(
        "algorithm complexity graph tree hash sort search dynamic programming "
        "recursive binary heap breadth depth stack queue".split()
    ),
    "problems": frozenset(
        "prove solve compute find show given let assume problem set".split()
    ),
}

TOKEN_PATTERN = re.compile(r"[a-z][a-z0-9\-]{2,}")


@dataclass
class DocumentAnalysis:
    """Analytic profile for one source document."""

    source_file: str
    topic: str
    subtopic: str
    title: str
    word_count: int
    chunk_count: int
    top_keywords: list[str] = field(default_factory=list)
    heading_phrases: list[str] = field(default_factory=list)


@dataclass
class CorpusAnalysis:
    """Aggregated analysis across the full ingested corpus."""

    document_count: int
    chunk_count: int
    total_words: int
    documents: list[DocumentAnalysis] = field(default_factory=list)
    domain_keywords: dict[str, list[str]] = field(default_factory=dict)


def tokenize(text: str) -> list[str]:
    """Lowercase tokenization with basic normalization."""
    return TOKEN_PATTERN.findall(text.lower())


def extract_heading_phrases(text: str, limit: int = 6) -> list[str]:
    """Pull likely section headings (title-case lines, chapter labels)."""
    patterns = [
        r"(?:Chapter|Lecture|Module|Week)\s+\d+[:\s\-–—]*(.*?)(?:\n|$)",
        r"(?:^|\n)([A-Z][A-Za-z0-9\s\-]{4,50})(?:\n)",
    ]
    found: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.MULTILINE):
            phrase = match.group(1).strip() if match.lastindex else match.group(0).strip()
            phrase = re.sub(r"\s+", " ", phrase)
            if 4 <= len(phrase) <= 60 and phrase.lower() not in STOPWORDS:
                found.append(phrase)
    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for phrase in found:
        key = phrase.lower()
        if key not in seen:
            seen.add(key)
            unique.append(phrase)
        if len(unique) >= limit:
            break
    return unique


def compute_tfidf_keywords(
    documents: list[SourceDocument],
    top_n: int = 8,
) -> dict[str, list[str]]:
    """Return top TF-IDF keywords per source file."""
    doc_terms: dict[str, Counter[str]] = {}
    df: Counter[str] = Counter()

    for doc in documents:
        tokens = [
            t
            for t in tokenize(" ".join(c.text for c in doc.chunks))
            if t not in STOPWORDS and len(t) > 2
        ]
        counts = Counter(tokens)
        doc_terms[doc.source_file] = counts
        for term in counts:
            df[term] += 1

    n_docs = max(len(documents), 1)
    result: dict[str, list[str]] = {}

    for doc in documents:
        scores: list[tuple[float, str]] = []
        counts = doc_terms.get(doc.source_file, Counter())
        for term, tf in counts.items():
            idf = math.log((n_docs + 1) / (df[term] + 1)) + 1.0
            boost = 1.5 if term in CONCEPT_HINTS.get(doc.topic, frozenset()) else 1.0
            scores.append((tf * idf * boost, term))
        scores.sort(reverse=True)
        result[doc.source_file] = [term for _, term in scores[:top_n]]

    return result


def analyze_corpus(
    documents: list[SourceDocument],
    keywords_per_doc: int = 8,
) -> CorpusAnalysis:
    """Build a full analytic profile of ingested content."""
    keywords_by_source = compute_tfidf_keywords(documents, top_n=keywords_per_doc)
    domain_term_counts: dict[str, Counter[str]] = defaultdict(Counter)

    doc_analyses: list[DocumentAnalysis] = []
    total_words = 0
    total_chunks = 0

    for doc in documents:
        full_text = "\n".join(c.text for c in doc.chunks)
        total_words += doc.total_words
        total_chunks += len(doc.chunks)

        keywords = keywords_by_source.get(doc.source_file, [])
        for kw in keywords:
            domain_term_counts[doc.topic][kw] += 1

        doc_analyses.append(
            DocumentAnalysis(
                source_file=doc.source_file,
                topic=doc.topic,
                subtopic=doc.subtopic,
                title=doc.title,
                word_count=doc.total_words,
                chunk_count=len(doc.chunks),
                top_keywords=keywords,
                heading_phrases=extract_heading_phrases(full_text),
            )
        )

    domain_keywords = {
        domain: [term for term, _ in counts.most_common(15)]
        for domain, counts in domain_term_counts.items()
    }

    return CorpusAnalysis(
        document_count=len(documents),
        chunk_count=total_chunks,
        total_words=total_words,
        documents=doc_analyses,
        domain_keywords=domain_keywords,
    )
