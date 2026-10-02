"""Practice-problem selection from the curriculum's problem bank (local, no generation model)."""

from __future__ import annotations

from ale.engine.curriculum import Concept, Problem


def select_problem(concept: Concept, difficulty: int, issue_counts: dict[str, int]) -> Problem:
    """Pick the least-seen problem at the requested difficulty (nearest difficulty if none exists).

    Ties break on bank order, so selection is deterministic for a given history.
    """
    if not concept.problems:
        raise ValueError(f"concept {concept.id} has no problems")
    ranked = sorted(
        enumerate(concept.problems),
        key=lambda ip: (abs(ip[1].difficulty - difficulty), issue_counts.get(ip[1].id, 0), ip[0]),
    )
    return ranked[0][1]


def public_problem(problem: Problem, problem_id: str) -> dict:
    """What a client may see. Never includes the answer key, signatures, or explanation."""
    return {
        "problem_id": problem_id,
        "bank_id": problem.id,
        "concept": problem.concept,
        "difficulty": problem.difficulty,
        "kind": problem.kind,
        "prompt": problem.prompt,
        "format": problem.format,
    }
