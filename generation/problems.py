"""Problem generation for practice sets."""

from __future__ import annotations

from engine.problem_generator import GeneratedProblem, ProblemGenerator

__all__ = ["ProblemGenerator", "GeneratedProblem", "generate_problem", "generate_problem_set"]


def generate_problem(user_state, concept: str | None = None) -> GeneratedProblem:
    return ProblemGenerator().generate_problem(user_state, concept)


def generate_problem_set(user_state, count: int = 3) -> list[GeneratedProblem]:
    return ProblemGenerator().generate_problem_set(user_state, count)
