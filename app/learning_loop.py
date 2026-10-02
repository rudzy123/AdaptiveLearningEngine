"""Unified adaptive learning loop orchestrating all engine components."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable

from config import SQLITE_DB_PATH
from engine.concepts import ConceptRegistry
from engine.curriculum import CurriculumService
from engine.evaluation import AnswerEvaluator, EvaluationResult
from engine.memory import MemoryStore
from engine.progression import ProgressionEngine
from engine.user_state import LearnerLevel
from generation.lesson import generate_lesson
from generation.problems import generate_problem
from app.session_log import SessionLogger

logger = logging.getLogger(__name__)

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]

TOPIC_ALIASES = {
    "linear algebra": "math",
    "linear_algebra": "math",
    "algorithms": "cs",
    "computer science": "cs",
    "mechanics": "physics",
    "thermodynamics": "physics",
}


@dataclass
class SessionConfig:
    """User session parameters."""

    user_id: str
    topic: str
    level: LearnerLevel = "beginner"
    problems_per_concept: int = 3
    max_concepts: int | None = 5


@dataclass
class ConceptSessionResult:
    """Summary after studying one concept."""

    concept: str
    problems_attempted: int
    problems_correct: int
    final_confidence: float
    progression_action: str
    duration_seconds: float = 0.0


@dataclass
class LearningSessionResult:
    """Full session output."""

    config: SessionConfig
    concepts_studied: list[str] = field(default_factory=list)
    concept_results: list[ConceptSessionResult] = field(default_factory=list)
    rag_available: bool = False


class AdaptiveLearningLoop:
    """
    Closed-loop tutor: curriculum → lesson (RAG) → problems → evaluate → progress.

    Integrates memory, deep evaluation, progression, and optional PDF retrieval.
    """

    def __init__(self) -> None:
        self.memory = MemoryStore()
        self.concepts = ConceptRegistry()
        self.curriculum = CurriculumService(self.concepts)
        self.progression = ProgressionEngine(self.memory, self.concepts)
        self.evaluator = AnswerEvaluator(self.memory, self.progression)
        self.session_log = SessionLogger()
        self.rag_available = SQLITE_DB_PATH.exists()

    @staticmethod
    def resolve_topic(raw: str) -> str:
        key = raw.lower().strip()
        return TOPIC_ALIASES.get(key, key)

    def run_interactive(
        self,
        config: SessionConfig,
        *,
        input_fn: InputFn,
        output_fn: OutputFn,
    ) -> LearningSessionResult:
        """Run session with CLI (or test) I/O callbacks."""
        result = LearningSessionResult(config=config, rag_available=self.rag_available)
        topic = self.resolve_topic(config.topic)

        if not self.rag_available:
            output_fn(
                "\nNote: No ingested PDF chunks found. Lessons will have limited context.\n"
                "  Run: python scripts/download_materials.py && python scripts/ingest_pdfs.py "
                "&& python tag_chunks.py\n"
            )

        self.memory.ensure_user_topic(
            config.user_id,
            topic,
            level=config.level,
            current_concept=self.concepts.get_first_concept(topic),
        )
        self.session_log.log(
            config.user_id, topic, "session_start",
            payload={"level": config.level, "rag": self.rag_available},
        )

        concept_list = self.curriculum.get_concepts_for_topic(topic)
        if not concept_list:
            concept_list = self.concepts.get_concepts_for_topic(topic)
        if config.max_concepts:
            concept_list = concept_list[: config.max_concepts]

        output_fn(f"\nCurriculum: {len(concept_list)} concepts — {', '.join(concept_list[:8])}")
        if len(concept_list) > 8:
            output_fn(f"  ... and {len(concept_list) - 8} more")

        result.concepts_studied = concept_list
        concept_index = 0

        while concept_index < len(concept_list):
            concept = concept_list[concept_index]
            output_fn(f"\n{'='*60}\nConcept: {self.concepts.label(concept)}\n{'='*60}")

            session_result = self._run_concept_interactive(
                config, topic, concept, input_fn, output_fn
            )
            result.concept_results.append(session_result)

            action = session_result.progression_action
            output_fn(
                f"\n--- Progress update ---\n"
                f"Confidence: {session_result.final_confidence:.0%} | "
                f"Score: {session_result.problems_correct}/{session_result.problems_attempted} | "
                f"Next: {action}\n"
            )

            if action == "advance":
                concept_index += 1
            elif action in ("reteach", "repeat"):
                output_fn("Re-teaching this concept with a simpler approach...\n")
            elif action == "review_previous":
                if concept_index > 0:
                    concept_index -= 1
                    output_fn("Reviewing previous concept...\n")
                else:
                    concept_index += 1
            else:
                concept_index += 1

            if input_fn("\nContinue to next unit? [Y/n]: ").lower() == "n":
                break

        self._print_session_summary(output_fn, result)
        self.session_log.log(
            config.user_id, topic, "session_end",
            payload={"concepts_completed": len(result.concept_results)},
        )
        return result

    def _run_concept_interactive(
        self,
        config: SessionConfig,
        topic: str,
        concept: str,
        input_fn: InputFn,
        output_fn: OutputFn,
    ) -> ConceptSessionResult:
        start = time.monotonic()
        self.memory.set_profile(config.user_id, topic, current_concept=concept)
        user_state = self.progression.build_user_state(config.user_id, topic)
        user_state.current_concept = concept
        user_state.focus_concepts = list(dict.fromkeys([concept, *user_state.weak_concepts]))

        # Lesson with RAG
        output_fn("\n## Lesson\n")
        try:
            lesson = generate_lesson(user_state)
            output_fn(lesson.render())
            has_pdf = lesson.has_pdf_content
        except FileNotFoundError:
            output_fn(
                f"_Teaching {self.concepts.label(concept)} ({user_state.difficulty}) — "
                "ingest PDFs for richer explanations._\n"
            )
            has_pdf = False

        self.session_log.log(
            config.user_id, topic, "lesson",
            concept=concept, payload={"has_pdf": has_pdf},
        )

        difficulties: list[LearnerLevel] = ["beginner", "intermediate", "advanced"]
        problems_correct = 0
        last_action = "repeat"

        output_fn("\n## Problems\n")
        for i in range(config.problems_per_concept):
            diff = difficulties[min(i, len(difficulties) - 1)]
            user_state.difficulty = diff
            try:
                problem = generate_problem(user_state, concept)
            except Exception as exc:
                output_fn(f"Could not generate problem: {exc}")
                logger.exception("problem_gen")
                break

            output_fn(
                f"\n### Problem {i + 1} ({diff})\n"
                f"{problem.question}\n"
            )
            if problem.hint and input_fn("Show hint? [y/N]: ").lower() == "y":
                output_fn(f"Hint: {problem.hint}")

            answer = input_fn("Your answer: ")
            if not answer.strip():
                output_fn("Skipping empty answer.\n")
                continue

            try:
                eval_result = self.evaluator.evaluate_and_update(
                    config.user_id,
                    topic,
                    concept,
                    answer,
                    problem.expected_answer,
                    difficulty=diff,
                    question=problem.question,
                )
            except Exception as exc:
                output_fn(f"Evaluation error: {exc}")
                logger.exception("evaluate")
                continue

            self._display_evaluation(output_fn, eval_result)
            self.session_log.log(
                config.user_id, topic, "answer",
                concept=concept,
                payload={
                    "correct": eval_result.correct,
                    "score": eval_result.score,
                    "error_type": eval_result.mistake_type,
                },
            )

            if eval_result.correct:
                problems_correct += 1
            if eval_result.next_step:
                last_action = eval_result.next_step.action

            user_state = self.progression.build_user_state(config.user_id, topic)

        record = self.memory.get_concept_progress(config.user_id, topic, concept)
        confidence = record.confidence_score if record else 0.0

        if "eval_result" in locals() and eval_result.next_step:
            last_action = eval_result.next_step.action
        else:
            last_action = self.progression.decide_next_step(
                config.user_id, concept, topic
            ).action

        return ConceptSessionResult(
            concept=concept,
            problems_attempted=config.problems_per_concept,
            problems_correct=problems_correct,
            final_confidence=confidence,
            progression_action=last_action,
            duration_seconds=time.monotonic() - start,
        )

    @staticmethod
    def _display_evaluation(output_fn: OutputFn, result: EvaluationResult) -> None:
        mark = "✓ Correct" if result.correct else "✗ Incorrect"
        output_fn(
            f"\n## Feedback\n"
            f"{mark} | Score: {result.score:.1f} | Error type: {result.mistake_type}\n"
            f"{result.feedback}\n"
        )
        if result.hint:
            output_fn(f"Hint: {result.hint}\n")
        if result.progress:
            output_fn(
                f"Confidence: {result.progress.confidence_score:.0%} "
                f"(Δ {result.confidence_adjustment:+.2f})\n"
            )
        if result.next_step:
            flags = []
            if result.next_step.accelerated:
                flags.append("accelerated")
            if result.next_step.difficulty_adjusted:
                flags.append("difficulty adjusted")
            extra = f" [{', '.join(flags)}]" if flags else ""
            output_fn(
                f"Progression: {result.next_step.action} | "
                f"difficulty={result.next_step.difficulty}{extra}\n"
            )

    @staticmethod
    def _print_session_summary(output_fn: OutputFn, result: LearningSessionResult) -> None:
        output_fn("\n" + "=" * 60 + "\nSESSION SUMMARY\n" + "=" * 60)
        for cr in result.concept_results:
            output_fn(
                f"  {cr.concept}: {cr.problems_correct}/{cr.problems_attempted} correct, "
                f"confidence={cr.final_confidence:.0%}, next={cr.progression_action}, "
                f"time={cr.duration_seconds:.0f}s"
            )
