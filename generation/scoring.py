"""Multi-layer scoring: exact, partial, and reasoning alignment."""

from __future__ import annotations

from dataclasses import dataclass

from config import (
    EVAL_CORRECT_THRESHOLD,
    EVAL_NUMERIC_TOLERANCE,
    EVAL_PARTIAL_THRESHOLD,
    EVAL_PERFECT_SCORE,
)
from generation.text_utils import (
    extract_numbers,
    has_reasoning_markers,
    jaccard_similarity,
    normalize_text,
    numeric_close,
    tokenize,
)

# Concept-specific keywords indicating sound reasoning approach
REASONING_KEYWORDS: dict[str, set[str]] = {
    "eigenvalues": {
        "eigenvalue", "eigenvector", "characteristic", "det", "determinant",
        "lambda", "av", "matrix",
    },
    "entropy": {
        "entropy", "disorder", "second law", "isolated", "increase",
        "thermodynamic", "system",
    },
    "vectors": {"dot", "cross", "magnitude", "vector", "component"},
    "sorting": {"merge", "quick", "partition", "complexity", "n log n", "compare"},
    "dynamic_programming": {
        "subproblem", "optimal", "memo", "overlap", "recurrence",
    },
    "energy": {"kinetic", "potential", "conservation", "work", "joule"},
    "momentum": {"momentum", "conservation", "collision", "impulse"},
    "determinants": {"determinant", "det", "matrix", "row", "column"},
    "graphs": {"vertex", "edge", "bfs", "dfs", "path", "tree"},
}


@dataclass
class LayerScores:
    """Scores from each evaluation layer."""

    exact: float
    partial: float
    reasoning: float
    combined: float
    is_exact_match: bool


def layer1_exact_match(user_answer: str, correct_answer: str) -> tuple[float, bool]:
    """
    Layer 1: Direct match with numeric tolerance.

    Returns (score 0-1, exact_flag).
    """
    ua = normalize_text(user_answer)
    ea = normalize_text(correct_answer)
    if not ua:
        return 0.0, False
    if ua == ea:
        return EVAL_PERFECT_SCORE, True
    if ea in ua or ua in ea:
        return EVAL_PERFECT_SCORE, True

    u_nums = extract_numbers(user_answer)
    e_nums = extract_numbers(correct_answer)
    if u_nums and e_nums:
        if len(u_nums) == len(e_nums):
            if all(numeric_close(a, b, EVAL_NUMERIC_TOLERANCE) for a, b in zip(u_nums, e_nums)):
                return EVAL_PERFECT_SCORE, True
        if any(numeric_close(u_nums[0], e) for e in e_nums):
            return 0.9, True

    u_tok, e_tok = tokenize(user_answer), tokenize(correct_answer)
    if e_tok:
        overlap = len(u_tok & e_tok) / len(e_tok)
        if overlap >= 0.95:
            return EVAL_PERFECT_SCORE, True
    return 0.0, False


def layer2_partial_credit(user_answer: str, correct_answer: str) -> float:
    """
    Layer 2: Partial credit for close answers (0.5–0.8 typical).

    Uses token Jaccard and numeric proximity.
    """
    u_tok, e_tok = tokenize(user_answer), tokenize(correct_answer)
    if not u_tok or not e_tok:
        return 0.0

    jaccard = jaccard_similarity(u_tok, e_tok)
    if jaccard >= 0.85:
        return 0.8
    if jaccard >= 0.65:
        return 0.65
    if jaccard >= 0.45:
        return 0.5

    u_nums = extract_numbers(user_answer)
    e_nums = extract_numbers(correct_answer)
    if u_nums and e_nums:
        for u in u_nums:
            for e in e_nums:
                if numeric_close(u, e, rel_tol=0.05):
                    return 0.55
    return 0.0


def layer3_reasoning_check(
    user_answer: str,
    correct_answer: str,
    concept: str,
) -> float:
    """
    Layer 3: Reward explanation-based answers that use correct approach.

    Checks for reasoning markers and concept-aligned vocabulary.
    """
    if not user_answer.strip():
        return 0.0

    score = 0.0
    if has_reasoning_markers(user_answer):
        score += 0.25

    concept_key = concept.lower().replace(" ", "_")
    keywords = REASONING_KEYWORDS.get(concept_key, set())
    if not keywords:
        keywords = tokenize(correct_answer)

    u_tok = tokenize(user_answer)
    if keywords:
        overlap = u_tok & keywords
        aligned = len(overlap) / max(len(keywords), 1)
        score += min(0.5, aligned * 0.6)
        if len(overlap) >= 2:
            score += 0.35

    e_tok = tokenize(correct_answer)
    if e_tok:
        overlap = len(u_tok & e_tok) / len(e_tok)
        score += min(0.25, overlap * 0.3)

    return min(1.0, score)


def combine_layers(
    user_answer: str,
    correct_answer: str,
    concept: str,
) -> LayerScores:
    """Run all layers and produce a final combined score."""
    exact_score, is_exact = layer1_exact_match(user_answer, correct_answer)
    if is_exact:
        return LayerScores(
            exact=exact_score,
            partial=exact_score,
            reasoning=1.0,
            combined=EVAL_PERFECT_SCORE,
            is_exact_match=True,
        )

    partial = layer2_partial_credit(user_answer, correct_answer)
    reasoning = layer3_reasoning_check(user_answer, correct_answer, concept)

    combined = max(exact_score, partial * 0.55 + reasoning * 0.45)
    if partial >= 0.5 and reasoning >= 0.3:
        combined = max(combined, 0.4 + partial * 0.3 + reasoning * 0.3)
    if reasoning >= 0.5 and partial < 0.5:
        combined = max(combined, 0.45 + reasoning * 0.25)

    combined = round(min(1.0, max(0.0, combined)), 3)

    return LayerScores(
        exact=exact_score,
        partial=partial,
        reasoning=reasoning,
        combined=combined,
        is_exact_match=False,
    )


def score_to_bucket(score: float) -> float:
    """Map continuous score to rubric buckets: 1.0, 0.7, 0.4, 0.0."""
    if score >= EVAL_CORRECT_THRESHOLD:
        return 1.0 if score >= 0.95 else 0.7
    if score >= EVAL_PARTIAL_THRESHOLD:
        return 0.4
    return 0.0
