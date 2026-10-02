"""Professor-level corrective feedback generation."""

from __future__ import annotations

from generation.error_detection import ErrorAnalysis, ErrorType
from generation.scoring import LayerScores


CONCEPT_REMINDERS: dict[str, str] = {
    "eigenvalues": (
        "Eigenvalues λ satisfy Av = λv for nonzero v. "
        "They are found from det(A − λI) = 0, not from det(A) alone."
    ),
    "entropy": (
        "For an isolated system, the second law states total entropy "
        "tends to increase — it does not stay constant during spontaneous change."
    ),
    "energy": (
        "Use conservation of energy only when the system is closed and "
        "you account for all energy forms (kinetic + potential + work/heat)."
    ),
    "momentum": (
        "Momentum conservation applies to isolated systems with no external impulse. "
        "Distinguish momentum from kinetic energy."
    ),
    "vectors": (
        "Dot product measures projection; cross product gives a perpendicular vector. "
        "Check dimensions before adding."
    ),
    "sorting": (
        "State the algorithm and its time complexity. "
        "Merge sort is O(n log n); naive bubble sort is O(n²)."
    ),
    "dynamic_programming": (
        "Identify overlapping subproblems and optimal substructure "
        "before writing a recurrence."
    ),
    "determinants": (
        "Determinant is a scalar property of a square matrix; "
        "it differs from eigenvalues."
    ),
}

ERROR_FEEDBACK: dict[ErrorType, str] = {
    "conceptual_error": (
        "Your answer is incorrect because the underlying principle was misapplied. "
        "{reminder} "
        "Re-read the definition, then try to justify each step before computing."
    ),
    "calculation_error": (
        "Your reasoning may be on the right track, but the final value is wrong. "
        "Walk through the algebra or arithmetic again — a small sign or factor error "
        "often causes this. {reminder}"
    ),
    "misinterpretation": (
        "You answered a related quantity, but not what the question asked for. "
        "{reminder} "
        "Identify exactly which variable or theorem the problem targets."
    ),
    "incomplete_answer": (
        "Your response is too brief to demonstrate understanding. "
        "State the method, show at least one intermediate step, then give the result."
    ),
    "guessing": (
        "This looks like a guess. Start by writing what is given, "
        "which law or definition applies, and why."
    ),
    "none": "Well done — your answer matches the expected result and reasoning.",
}


def generate_feedback(
    *,
    concept: str,
    user_answer: str,
    correct_answer: str,
    error: ErrorAnalysis,
    layer: LayerScores,
    is_correct: bool,
    score: float,
) -> str:
    """
    Build structured feedback: why wrong, concept reconnect, brief correct path.

    Does not dump the final answer immediately unless score is very low.
    """
    concept_key = concept.lower().replace(" ", "_")
    reminder = CONCEPT_REMINDERS.get(
        concept_key,
        f"Review the core ideas of {concept.replace('_', ' ')} in your materials.",
    )

    if is_correct:
        msg = ERROR_FEEDBACK["none"]
        if layer.reasoning >= 0.3 and has_explanation(user_answer):
            msg += " Good use of reasoning in your explanation."
        return msg

    template = ERROR_FEEDBACK.get(error.error_type, ERROR_FEEDBACK["conceptual_error"])
    body = template.format(reminder=reminder)

    if error.error_type == "conceptual_error" and layer.partial >= 0.4:
        body += (
            " You had some correct vocabulary — tighten the logical chain "
            "from assumptions to conclusion."
        )

    if score >= 0.4 and not is_correct:
        body += (
            f"\n\nYou earned partial credit (score {score:.1f}). "
            "You're closer than a blank wrong answer — refine the weak step."
        )

    if score < 0.3:
        body += (
            f"\n\nCorrect approach (outline): start from {reminder} "
            f"Then compare your result to the expected form: «{correct_answer[:80]}»."
        )
    else:
        body += "\n\nTry once more before viewing the full solution."

    return body.strip()


def has_explanation(text: str) -> bool:
    return len(text.split()) > 8 and any(
        w in text.lower() for w in ("because", "since", "therefore", "so")
    )
