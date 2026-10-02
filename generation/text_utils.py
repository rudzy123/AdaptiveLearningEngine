"""Text normalization and parsing helpers for evaluation."""

from __future__ import annotations

import re
from typing import Any

NUMERIC_PATTERN = re.compile(r"-?\d+\.?\d*(?:[eE][+-]?\d+)?")
WORD_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def normalize_text(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation for comparison."""
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s\.\-]", " ", text)
    return text.strip()


def tokenize(text: str) -> set[str]:
    return set(WORD_PATTERN.findall(normalize_text(text)))


def extract_numbers(text: str) -> list[float]:
    """Parse numeric literals from answer text."""
    values: list[float] = []
    for match in NUMERIC_PATTERN.findall(text):
        try:
            values.append(float(match))
        except ValueError:
            continue
    return values


def numeric_close(a: float, b: float, rel_tol: float = 1e-2, abs_tol: float = 1e-6) -> bool:
    return abs(a - b) <= max(abs_tol, rel_tol * max(abs(a), abs(b), 1.0))


def jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def has_reasoning_markers(text: str) -> bool:
    """Detect step-by-step or explanatory phrasing."""
    markers = (
        "because", "therefore", "since", "step", "first", "then",
        "thus", "so ", "hence", "implies", "we have", "it follows",
    )
    lower = text.lower()
    return any(m in lower for m in markers)
