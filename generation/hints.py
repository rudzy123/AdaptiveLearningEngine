"""Graduated hint generation (3 levels)."""

from __future__ import annotations

from generation.error_detection import ErrorType

HINT_BANK: dict[str, list[str]] = {
    "eigenvalues": [
        "Recall: λ is a scalar where Av = λv. What equation defines λ?",
        "Set up det(A − λI) = 0 and solve for λ.",
        "For diagonal matrices, eigenvalues appear on the diagonal.",
    ],
    "entropy": [
        "Think about the second law for an isolated system.",
        "Does entropy tend to increase, decrease, or stay fixed spontaneously?",
        "Entropy increases for isolated systems undergoing irreversible change.",
    ],
    "vectors": [
        "Write both vectors component-wise.",
        "For dot product: multiply matching components and sum.",
        "Dot product of [1,2] and [3,4] is 1×3 + 2×4.",
    ],
    "sorting": [
        "Which algorithm divides the array recursively?",
        "Merge sort: split, sort halves, merge — what is its complexity?",
        "Worst-case time for merge sort is O(n log n).",
    ],
    "dynamic_programming": [
        "Can you break the problem into smaller overlapping subproblems?",
        "Write a recurrence relating opt(n) to smaller cases.",
        "Use memoization or tabulation after defining the recurrence.",
    ],
    "energy": [
        "List initial and final energy forms.",
        "Account for kinetic and potential energy; is work done on the system?",
        "Apply ΔE = W + Q if non-isolated; otherwise mechanical energy conservation.",
    ],
    "general": [
        "What quantity is the question asking for?",
        "Which principle from the lesson applies here?",
        "Compare your final expression to the expected form after checking units.",
    ],
}

ERROR_HINT_ADJUST: dict[ErrorType, str] = {
    "calculation_error": "Recheck signs and arithmetic on the last step.",
    "conceptual_error": "Re-state the governing law before calculating.",
    "misinterpretation": "Re-read the prompt: which variable is requested?",
    "incomplete_answer": "Include method + at least one intermediate step.",
    "guessing": "Write what is given, then which theorem applies.",
}


def generate_hints(
    concept: str,
    error_type: ErrorType,
    *,
    level: int = 1,
) -> str:
    """
    Return a hint at the requested level (1=nudge, 2=stronger, 3=near solution).

    `level` can be incremented across retries for the same problem.
    """
    concept_key = concept.lower().replace(" ", "_")
    hints = HINT_BANK.get(concept_key, HINT_BANK["general"])
    idx = min(max(level - 1, 0), len(hints) - 1)
    base = hints[idx]

    extra = ERROR_HINT_ADJUST.get(error_type, "")
    if extra and level == 1:
        return f"{base} ({extra})"
    return base


def all_hints(concept: str, error_type: ErrorType) -> list[str]:
    """Return all three hint levels for display or logging."""
    return [generate_hints(concept, error_type, level=i) for i in range(1, 4)]
