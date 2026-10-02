"""Classify learner mistakes into actionable error types."""

from __future__ import annotations

import re
from dataclasses import dataclass

from generation.scoring import LayerScores
from generation.text_utils import (
    extract_numbers,
    has_reasoning_markers,
    jaccard_similarity,
    normalize_text,
    numeric_close,
    tokenize,
)

ErrorType = str  # conceptual_error | calculation_error | misinterpretation | incomplete_answer | guessing | none

# Phrases suggesting wrong conceptual model
CONCEPTUAL_MISCONCEPTIONS: dict[str, list[str]] = {
    "entropy": [
        "decrease entropy isolated",
        "entropy always zero",
        "entropy destroys",
    ],
    "energy": [
        "energy created",
        "perpetual motion",
        "energy disappears",
    ],
    "eigenvalues": [
        "determinant always 1",
        "eigenvalue is zero always",
    ],
}


@dataclass
class ErrorAnalysis:
    """Result of error classification."""

    error_type: ErrorType
    confidence: float
    details: str


def detect_incomplete_answer(user_answer: str, correct_answer: str) -> bool:
    """True if answer is empty or far shorter than expected."""
    ua = normalize_text(user_answer)
    if not ua or len(ua) < 3:
        return True
    ea = normalize_text(correct_answer)
    if ea and len(ua) < len(ea) * 0.25:
        return True
    if ua in ("idk", "i dont know", "don't know", "no idea", "?"):
        return True
    return False


def detect_guessing(user_answer: str, correct_answer: str, layer: LayerScores) -> bool:
    """Very short, no reasoning, low overlap — likely a guess."""
    ua = normalize_text(user_answer)
    if len(ua.split()) <= 2 and not has_reasoning_markers(user_answer):
        u_tok = tokenize(user_answer)
        e_tok = tokenize(correct_answer)
        if e_tok and jaccard_similarity(u_tok, e_tok) < 0.2:
            return True
    if layer.combined < 0.15 and len(ua) < 15:
        return True
    return False


def detect_calculation_error(user_answer: str, correct_answer: str) -> bool:
    """
    Numbers present but wrong; vocabulary otherwise aligns.

    Suggests arithmetic slip rather than conceptual gap.
    """
    u_nums = extract_numbers(user_answer)
    e_nums = extract_numbers(correct_answer)
    if not u_nums or not e_nums:
        return False

    u_tok, e_tok = tokenize(user_answer), tokenize(correct_answer)
    vocab_overlap = jaccard_similarity(u_tok, e_tok) if e_tok else 0.0

    if vocab_overlap >= 0.4:
        close_any = any(
            numeric_close(u, e, rel_tol=0.2) for u in u_nums for e in e_nums
        )
        exact_any = any(
            numeric_close(u, e) for u in u_nums for e in e_nums
        )
        if not exact_any and (close_any or u_nums != e_nums):
            return True
    return False


def detect_misinterpretation(user_answer: str, correct_answer: str, concept: str) -> bool:
    """
    Answer addresses a different but related quantity or formula.

    e.g. answering with determinant when eigenvalues asked.
    """
    pairs = [
        ({"eigenvalue", "eigenvector", "lambda"}, {"determinant", "det", "trace"}),
        ({"entropy"}, {"enthalpy", "heat", "temperature only"}),
        ({"momentum"}, {"energy", "force only"}),
        ({"bfs", "breadth"}, {"dfs", "depth"}),
    ]
    u_tok = tokenize(user_answer)
    e_tok = tokenize(correct_answer)
    concept_tok = tokenize(concept.replace("_", " "))

    for expected_set, wrong_set in pairs:
        scope = e_tok | concept_tok
        if any(k.rstrip("s") in " ".join(scope) or k in " ".join(scope) for k in expected_set):
            if wrong_set & u_tok and not (expected_set & u_tok):
                return True
    if "eigen" in concept.lower() and {"determinant", "det", "trace"} & u_tok:
        if not ({"eigenvalue", "eigenvector", "lambda"} & u_tok):
            return True
    return False


def detect_conceptual_error(
    user_answer: str,
    correct_answer: str,
    concept: str,
    layer: LayerScores,
) -> bool:
    """Wrong model or principle despite substantive answer."""
    lower = user_answer.lower()
    concept_key = concept.lower().replace(" ", "_")
    for phrase in CONCEPTUAL_MISCONCEPTIONS.get(concept_key, []):
        if phrase in lower:
            return True

    if layer.reasoning < 0.15 and layer.partial < 0.35 and layer.combined < 0.35:
        if len(normalize_text(user_answer)) > 20:
            return True
    return False


def classify_error(
    user_answer: str,
    correct_answer: str,
    concept: str,
    layer: LayerScores,
    is_correct: bool,
) -> ErrorAnalysis:
    """
    Layer 4: Assign dominant error type using priority rules.

    Order: incomplete → guessing → misinterpretation → calculation → conceptual
    """
    if is_correct:
        return ErrorAnalysis("none", 1.0, "Answer accepted.")

    if detect_incomplete_answer(user_answer, correct_answer):
        return ErrorAnalysis(
            "incomplete_answer", 0.9, "Response too short or missing key content."
        )

    if detect_guessing(user_answer, correct_answer, layer):
        return ErrorAnalysis("guessing", 0.85, "Answer appears to be a guess.")

    if detect_misinterpretation(user_answer, correct_answer, concept):
        return ErrorAnalysis(
            "misinterpretation",
            0.8,
            "You may be solving a related but different quantity.",
        )

    if detect_calculation_error(user_answer, correct_answer):
        return ErrorAnalysis(
            "calculation_error", 0.75, "Approach may be right; check arithmetic."
        )

    if detect_conceptual_error(user_answer, correct_answer, concept, layer):
        return ErrorAnalysis(
            "conceptual_error", 0.85, "Underlying concept application looks incorrect."
        )

    if layer.reasoning >= 0.4 and layer.partial < 0.4:
        return ErrorAnalysis(
            "conceptual_error", 0.7, "Reasoning present but conclusion does not match."
        )

    return ErrorAnalysis("conceptual_error", 0.6, "Answer does not match expected result.")
