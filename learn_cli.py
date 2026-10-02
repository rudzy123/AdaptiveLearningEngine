#!/usr/bin/env python3
"""
Interactive CLI for the Adaptive Learning Engine closed-loop MVP.

Flow: topic → lesson → problems → evaluate → update memory → next step
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.concepts import ConceptRegistry  # noqa: E402
from engine.evaluation import AnswerEvaluator  # noqa: E402
from engine.lesson_generator import LessonGenerator  # noqa: E402
from engine.memory import MemoryStore  # noqa: E402
from engine.problem_generator import ProblemGenerator  # noqa: E402
from engine.progression import ProgressionEngine  # noqa: E402
from pipeline.logging_setup import setup_logging  # noqa: E402

TOPIC_ALIASES = {
    "1": "math",
    "2": "physics",
    "3": "cs",
    "math": "math",
    "linear_algebra": "math",
    "linear algebra": "math",
    "physics": "physics",
    "mechanics": "physics",
    "cs": "cs",
    "algorithms": "cs",
    "computer science": "cs",
}


def prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye!")
        sys.exit(0)


def resolve_topic(raw: str) -> str:
    key = raw.lower().strip()
    return TOPIC_ALIASES.get(key, key)


def print_banner() -> None:
    print(
        """
╔══════════════════════════════════════════════╗
║     Adaptive Learning Engine (local MVP)     ║
╚══════════════════════════════════════════════╝
        """
    )


def choose_topic() -> str:
    print("Choose a topic:")
    print("  1) math (linear algebra)")
    print("  2) physics")
    print("  3) cs (algorithms)")
    raw = prompt("Topic [1]: ") or "1"
    return resolve_topic(raw)


def show_progress_summary(memory: MemoryStore, user_id: str, topic: str) -> None:
    progress = memory.get_user_progress(user_id, topic)
    if not progress:
        print("\n(No progress yet for this topic.)\n")
        return
    print("\n--- Your progress ---")
    for p in progress:
        filled = int(p.confidence_score * 10)
        bar = "█" * filled + "░" * (10 - filled)
        print(
            f"  {p.concept:24s} [{bar}] "
            f"{p.confidence_score:.0%} ({p.correct_count}/{p.attempts})"
        )
    weak = memory.get_weak_areas(user_id, topic)
    strong = memory.get_strong_areas(user_id, topic)
    if weak:
        print(f"  Weak: {', '.join(w.concept for w in weak[:5])}")
    if strong:
        print(f"  Strong: {', '.join(s.concept for s in strong[:5])}")
    print()


def run_lesson(lesson_gen: LessonGenerator, user_state) -> None:
    print("\nGenerating lesson...")
    try:
        lesson = lesson_gen.generate_lesson(user_state)
        print("\n" + lesson.render())
    except FileNotFoundError as exc:
        print(f"\n⚠ {exc}")
        print("Run: python ingest_pdfs.py && python tag_chunks.py\n")


def run_problem(
    problem_gen: ProblemGenerator,
    evaluator: AnswerEvaluator,
    memory: MemoryStore,
    concepts: ConceptRegistry,
    user_state,
    user_id: str,
    topic: str,
) -> None:
    problem = problem_gen.generate_problem(user_state)
    print(f"\n--- Problem ({problem.difficulty}) ---")
    print(f"Concept: {concepts.label(problem.concept)}")
    print(problem.question)
    if problem.hint and prompt("Show hint? [y/N]: ").lower() == "y":
        print(f"Hint: {problem.hint}")

    answer = prompt("\nYour answer: ")
    result = evaluator.evaluate_and_update(
        user_id,
        topic,
        problem.concept,
        answer,
        problem.expected_answer,
        difficulty=problem.difficulty,
        question=problem.question,
    )
    mark = "✓" if result.correct else "✗"
    print(f"\n{mark} Score: {result.score:.1f} | Error: {result.mistake_type}")
    print(result.feedback)
    if result.hint:
        print(f"\nHint: {result.hint}")
        if result.hints and len(result.hints) > 1:
            print(f"(Further hints available: {len(result.hints) - 1} more)")
    if result.progress:
        print(
            f"\nConfidence in {problem.concept}: "
            f"{result.progress.confidence_score:.0%} "
            f"(Δ {result.confidence_adjustment:+.2f})"
        )
    if result.next_step:
        target = result.next_step.next_concept or result.next_step.concept
        memory.set_profile(user_id, topic, current_concept=target)
        accel = " (accelerated)" if result.next_step.accelerated else ""
        lowered = " (difficulty lowered)" if result.next_step.difficulty_adjusted else ""
        print(
            f"\nProgression: {result.next_step.action} | "
            f"difficulty={result.next_step.difficulty}{accel}{lowered}"
        )


def run_session() -> int:
    setup_logging("learn_cli")
    print_banner()

    user_id = prompt("Your user id [learner1]: ") or "learner1"
    topic = choose_topic()

    memory = MemoryStore()
    concepts = ConceptRegistry()
    progression = ProgressionEngine(memory, concepts)
    evaluator = AnswerEvaluator(memory, progression)
    lesson_gen = LessonGenerator()
    problem_gen = ProblemGenerator()

    first_concept = concepts.get_first_concept(topic)
    memory.ensure_user_topic(user_id, topic, current_concept=first_concept)

    print(f"\nHello {user_id}! Topic: {topic}")
    show_progress_summary(memory, user_id, topic)

    while True:
        user_state = progression.build_user_state(user_id, topic)
        decision = progression.decide_next_step(
            user_id, user_state.current_concept, topic
        )
        print(f"\n► Next step: {decision.action} — {decision.message}")

        if decision.focus_concepts:
            user_state.focus_concepts = decision.focus_concepts
        user_state.difficulty = decision.difficulty
        user_state.needs_reteach = decision.action == "reteach"
        if decision.next_concept:
            user_state.current_concept = decision.next_concept

        cmd = prompt(
            "\n[L]esson [P]roblem [B]oth [S]ummary [Q]uit [Enter=both]: "
        ).lower() or "b"

        if cmd in ("q", "quit", "exit"):
            print("Session saved. See you next time!")
            break
        if cmd in ("s", "summary"):
            show_progress_summary(memory, user_id, topic)
            continue
        if cmd in ("l", "lesson"):
            run_lesson(lesson_gen, user_state)
            continue
        if cmd in ("p", "problem"):
            run_problem(
                problem_gen, evaluator, memory, concepts,
                user_state, user_id, topic,
            )
            continue
        # both (default)
        run_lesson(lesson_gen, user_state)
        run_problem(
            problem_gen, evaluator, memory, concepts,
            user_state, user_id, topic,
        )

    return 0


def main() -> int:
    return run_session()


if __name__ == "__main__":
    raise SystemExit(main())
