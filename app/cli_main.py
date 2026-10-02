#!/usr/bin/env python3
"""
Adaptive Learning Engine — CLI entry point.

Run: python app/cli_main.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.learning_loop import AdaptiveLearningLoop, SessionConfig  # noqa: E402
from engine.memory import MemoryStore  # noqa: E402
from pipeline.logging_setup import setup_logging  # noqa: E402


def prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye!")
        sys.exit(0)


def print_banner() -> None:
    print(
        """
╔══════════════════════════════════════════════╗
║     Adaptive Learning Engine (local)         ║
╚══════════════════════════════════════════════╝
        """
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Adaptive Learning Engine CLI")
    parser.add_argument("--user", default="default", help="User profile id")
    parser.add_argument("--topic", default="", help="Topic (math, physics, cs)")
    parser.add_argument(
        "--level",
        default="beginner",
        choices=["beginner", "intermediate", "advanced"],
    )
    parser.add_argument("--problems", type=int, default=3, help="Problems per concept")
    parser.add_argument("--max-concepts", type=int, default=5, help="Max concepts per session")
    return parser.parse_args()


def choose_topic(args: argparse.Namespace) -> str:
    if args.topic:
        return AdaptiveLearningLoop.resolve_topic(args.topic)
    print("Topics: math (linear algebra), physics, cs (algorithms)")
    raw = prompt("Enter topic [math]: ") or "math"
    return AdaptiveLearningLoop.resolve_topic(raw)


def show_progress(memory: MemoryStore, user_id: str, topic: str) -> None:
    progress = memory.get_user_progress(user_id, topic)
    if not progress:
        return
    print("\n--- Saved progress ---")
    for p in progress[:12]:
        filled = int(p.confidence_score * 10)
        bar = "█" * filled + "░" * (10 - filled)
        print(
            f"  {p.concept:24s} [{bar}] "
            f"{p.confidence_score:.0%} ({p.correct_count}/{p.attempts})"
        )
    print()


def main() -> int:
    setup_logging("adaptive_learning_engine")
    print_banner()
    args = parse_args()

    topic = choose_topic(args)
    level_raw = args.level
    if not args.topic:
        level_in = prompt(f"Level [beginner/intermediate/advanced] ({level_raw}): ")
        if level_in in ("beginner", "intermediate", "advanced"):
            level_raw = level_in

    loop = AdaptiveLearningLoop()
    show_progress(loop.memory, args.user, topic)

    config = SessionConfig(
        user_id=args.user,
        topic=topic,
        level=level_raw,  # type: ignore[arg-type]
        problems_per_concept=max(1, args.problems),
        max_concepts=max(1, args.max_concepts),
    )

    loop.run_interactive(
        config,
        input_fn=prompt,
        output_fn=print,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
