#!/usr/bin/env python3
"""
Adaptive Learning Engine (ALE) demo.

Runs a complete deterministic learning cycle:
start_topic -> get_lesson -> get_problem -> submit_answer -> next_step -> progress
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.learning_session import LearningSession  # noqa: E402


def print_section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def run_demo(user_id: str = "ale_demo_user") -> None:
    """Execute one end-to-end ALE tutoring loop for demonstration."""
    session = LearningSession()

    print_section("1) Start Topic")
    started = session.start_topic(user_id, "linear algebra", "beginner")
    print(json.dumps(started, indent=2))

    print_section("2) Lesson")
    lesson = session.get_lesson(user_id)
    print(f"Concept: {lesson['concept']}")
    print("Lesson preview:")
    print(lesson["lesson"][:700] + ("..." if len(lesson["lesson"]) > 700 else ""))
    print(f"RAG chunks: {len(lesson.get('chunks', []))}")

    print_section("3) Problem")
    problem = session.get_problem(user_id)
    print(json.dumps(problem, indent=2))

    print_section("4) Submit Answer")
    # Intentionally imperfect to demonstrate feedback and learning_signal.
    answer = "I think eigenvalues are the determinant only."
    evaluation = session.submit_answer(user_id, answer)
    print(json.dumps(evaluation, indent=2))

    print_section("5) Decide Next Step")
    step = session.decide_next_step(user_id)
    print(json.dumps(step, indent=2))

    print_section("6) Progress Snapshot")
    progress = session.get_progress(user_id)
    print(f"Topic: {progress['topic']}")
    for concept in progress["concepts"][:8]:
        print(
            f"- {concept.get('label', concept['name'])}: "
            f"{concept['confidence']:.0%} (attempts={concept.get('attempts', 0)})"
        )

    print("\nDemo complete. ALE state is persisted in SQLite under data/*.db.")


if __name__ == "__main__":
    run_demo()

