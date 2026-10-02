"""Simulated learners: validate that the loop *behaves* adaptively, not just that functions return values.

Each persona answers from the problem bank (correct answers, known wrong-answer signatures,
off-by-one slips, or "I don't know"). The simulator drives the real Tutor end to end and records
the trajectory, so tests can assert behavior such as "a careless learner is never reset to a
full reteach for arithmetic slips" or "a struggling learner is reteached after three failures".

    python -m ale simulate
"""

from __future__ import annotations

import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ale.engine.curriculum import Problem
from ale.engine.tutor import Tutor


# --------------------------------------------------------------------------
# Answer generators
# --------------------------------------------------------------------------

def _fmt(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


def correct_answer(problem: Problem) -> tuple[str, str]:
    """(answer, reasoning) that should pass with full reasoning alignment."""
    reasoning = "Reasoning: " + ", ".join(problem.reasoning_terms)
    if problem.kind == "numeric":
        return ", ".join(_fmt(x) for x in problem.answer), reasoning
    if problem.kind == "complexity":
        return f"O({problem.answer[0]})", reasoning
    if problem.accepted:
        return problem.accepted[0], reasoning
    return problem.explanation, reasoning


def wrong_answer(problem: Problem, error_type: str) -> str:
    """An answer that the evaluator should type as `error_type` where the bank supports it."""
    def example(sig) -> str:
        if sig.numbers is not None:
            return ", ".join(_fmt(x) for x in sig.numbers)
        return sig.example or "I am not sure how to start"

    if error_type == "incomplete":
        if problem.kind == "numeric" and len(problem.answer) > 1:
            return _fmt(problem.answer[0])
        return "I don't know"
    for sig in problem.signatures:
        if sig.type == error_type:
            return example(sig)
    if error_type == "calculation_error" and problem.kind == "numeric":
        values = list(problem.answer)
        values[0] = values[0] + 1
        return ", ".join(_fmt(x) for x in values)
    for sig in problem.signatures:  # fall back to any known wrong answer
        return example(sig)
    return "I don't know"


# --------------------------------------------------------------------------
# Personas
# --------------------------------------------------------------------------

Policy = Callable[[Problem, int], tuple[str, str]]  # (problem, attempts_on_concept) -> (answer, reasoning)


@dataclass(frozen=True)
class Persona:
    name: str
    description: str
    policy: Policy


def _mastery(p: Problem, n: int) -> tuple[str, str]:
    return correct_answer(p)


def _careless(p: Problem, n: int) -> tuple[str, str]:
    if n < 2 and p.kind == "numeric":
        return wrong_answer(p, "calculation_error"), ""
    return correct_answer(p)


def _confused(p: Problem, n: int) -> tuple[str, str]:
    if n < 1:
        return wrong_answer(p, "conceptual_error"), ""
    return correct_answer(p)


def _struggling(p: Problem, n: int) -> tuple[str, str]:
    return "I don't know", ""


PERSONAS = {
    "mastery": Persona("mastery", "answers correctly with reasoning", _mastery),
    "careless": Persona("careless", "makes arithmetic slips on its first two tries per concept", _careless),
    "confused": Persona("confused", "has a conceptual misunderstanding on the first try per concept", _confused),
    "struggling": Persona("struggling", "never produces an answer", _struggling),
}


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

def run_persona(
    persona: Persona,
    tutor: Tutor,
    user_id: str,
    topic: str,
    max_steps: int = 40,
) -> dict:
    tutor.start_topic(user_id, topic)
    trajectory: list[dict] = []
    for step in range(1, max_steps + 1):
        state = tutor.state(user_id)
        if state["status"] == "completed":
            break
        tutor.get_lesson(user_id)
        issued = tutor.get_problem(user_id)
        problem = tutor.curriculum.problem(issued["bank_id"])
        attempts_so_far = tutor.store.get_memory(user_id, issued["concept"], 0.0).attempts
        answer, reasoning = persona.policy(problem, attempts_so_far)
        result = tutor.submit_answer(user_id, issued["problem_id"], answer, reasoning)
        trajectory.append(
            {
                "step": step,
                "concept": result["concept"],
                "problem": problem.id,
                "difficulty": problem.difficulty,
                "answer": answer,
                "error_type": result["error_type"],
                "score": result["score"],
                "confidence": result["memory"]["confidence_after"],
                "action": result["next_step"]["action"],
                "rule": result["next_step"]["rule"],
                "lesson_level": result["next_step"]["lesson_level"],
            }
        )
    completed = tutor.state(user_id)["status"] == "completed"
    return {
        "persona": persona.name,
        "description": persona.description,
        "completed": completed,
        "steps": len(trajectory),
        "actions": dict(Counter(t["action"] for t in trajectory)),
        "trajectory": trajectory,
    }


def run_all(topic: str = "linear algebra", db: str | Path | None = None, max_steps: int = 40) -> list[dict]:
    path = Path(db) if db else Path(tempfile.mkdtemp(prefix="ale_sim_")) / "sim.db"
    tutor = Tutor(path)
    return [run_persona(p, tutor, f"sim_{p.name}", topic, max_steps) for p in PERSONAS.values()]


def format_report(results: list[dict]) -> str:
    lines = ["Simulated learners on the real adaptive loop (local, deterministic)", ""]
    for r in results:
        lines.append(
            f"{r['persona']:<11} {r['description']}\n"
            f"            steps={r['steps']:<3} completed={r['completed']!s:<5} actions={r['actions']}"
        )
    return "\n".join(lines)
