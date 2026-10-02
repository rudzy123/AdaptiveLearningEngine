"""State controller for the web learning panel (lesson → problem → evaluate)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Literal

from config import SQLITE_DB_PATH
from engine.concepts import ConceptRegistry
from engine.curriculum import CurriculumService
from engine.evaluation import AnswerEvaluator, EvaluationResult
from engine.memory import MemoryStore
from engine.problem_generator import GeneratedProblem
from engine.progression import ProgressionEngine
from engine.user_state import LearnerLevel
from generation.lesson import generate_lesson
from generation.problems import generate_problem
from app.learning_loop import AdaptiveLearningLoop, SessionConfig
from app.session_log import SessionLogger

logger = logging.getLogger(__name__)

PanelPhase = Literal[
    "setup",
    "lesson",
    "problem",
    "feedback",
    "concept_summary",
    "done",
]

DIFFICULTY_SEQUENCE: list[LearnerLevel] = ["beginner", "intermediate", "advanced"]


@dataclass
class PanelEvaluationView:
    """Evaluation payload formatted for the UI."""

    correct: bool
    score: float
    mistake_type: str
    feedback: str
    hint: str
    confidence: float
    confidence_delta: float
    progression_action: str
    progression_message: str
    difficulty: str

    @classmethod
    def from_result(cls, result: EvaluationResult) -> PanelEvaluationView:
        confidence = 0.0
        if result.progress:
            confidence = result.progress.confidence_score
        action = ""
        message = ""
        difficulty = ""
        if result.next_step:
            action = result.next_step.action
            message = result.next_step.message
            difficulty = result.next_step.difficulty
        return cls(
            correct=result.correct,
            score=result.score,
            mistake_type=result.mistake_type,
            feedback=result.feedback,
            hint=result.hint,
            confidence=confidence,
            confidence_delta=result.confidence_adjustment,
            progression_action=action,
            progression_message=message,
            difficulty=difficulty,
        )


@dataclass
class LearningPanelState:
    """Serializable session state for Streamlit."""

    phase: PanelPhase = "setup"
    config: SessionConfig | None = None
    topic: str = ""
    concepts: list[str] = field(default_factory=list)
    concept_index: int = 0
    problem_index: int = 0
    problems_correct: int = 0
    lesson_markdown: str = ""
    lesson_has_pdf: bool = False
    lesson_payload: dict | None = None
    current_problem: GeneratedProblem | None = None
    current_difficulty: LearnerLevel = "beginner"
    last_evaluation: PanelEvaluationView | None = None
    concept_progression_action: str = ""
    rag_available: bool = False
    error_message: str = ""


class LearningPanelController:
    """
    Drives one concept at a time: load lesson, show problems sequentially,
    evaluate answers, advance on progression rules.
    """

    def __init__(self) -> None:
        self.memory = MemoryStore()
        self.concepts = ConceptRegistry()
        self.curriculum = CurriculumService(self.concepts)
        self.progression = ProgressionEngine(self.memory, self.concepts)
        self.evaluator = AnswerEvaluator(self.memory, self.progression)
        self.session_log = SessionLogger()
        self.rag_available = SQLITE_DB_PATH.exists()

    def start_session(self, config: SessionConfig) -> LearningPanelState:
        """Initialize topic, curriculum, and first concept lesson."""
        topic = AdaptiveLearningLoop.resolve_topic(config.topic)
        concept_list = self.curriculum.get_concepts_for_topic(topic)
        if not concept_list:
            concept_list = self.concepts.get_concepts_for_topic(topic)
        if config.max_concepts:
            concept_list = concept_list[: config.max_concepts]
        if not concept_list:
            return LearningPanelState(
                phase="setup",
                error_message=f"No concepts found for topic '{topic}'.",
            )

        self.memory.ensure_user_topic(
            config.user_id,
            topic,
            level=config.level,
            current_concept=concept_list[0],
        )
        self.session_log.log(
            config.user_id, topic, "session_start",
            payload={"level": config.level, "ui": "panel"},
        )

        state = LearningPanelState(
            phase="lesson",
            config=config,
            topic=topic,
            concepts=concept_list,
            concept_index=0,
            rag_available=self.rag_available,
        )
        return self._load_lesson(state)

    def _current_concept(self, state: LearningPanelState) -> str:
        return state.concepts[state.concept_index]

    def _load_lesson(self, state: LearningPanelState) -> LearningPanelState:
        """Generate and store lesson markdown for the current concept."""
        config = state.config
        assert config is not None
        concept = self._current_concept(state)
        self.memory.set_profile(config.user_id, state.topic, current_concept=concept)

        user_state = self.progression.build_user_state(config.user_id, state.topic)
        user_state.current_concept = concept
        user_state.focus_concepts = list(
            dict.fromkeys([concept, *user_state.weak_concepts])
        )

        try:
            lesson = generate_lesson(user_state)
            state.lesson_markdown = lesson.render()
            state.lesson_has_pdf = lesson.has_pdf_content
            from api.lesson_serializer import lesson_to_api

            state.lesson_payload = lesson_to_api(lesson, self.concepts)
        except FileNotFoundError:
            state.lesson_markdown = (
                f"# {self.concepts.label(concept)}\n\n"
                f"Teaching **{self.concepts.label(concept)}** at "
                f"**{user_state.difficulty}** level.\n\n"
                "_Ingest PDFs for richer lessons: "
                "`python scripts/ingest_pdfs.py` then `python tag_chunks.py`_"
            )
            state.lesson_has_pdf = False
            state.lesson_payload = {
                "concept_id": concept,
                "concept_label": self.concepts.label(concept),
                "title": self.concepts.label(concept),
                "topic": state.topic,
                "difficulty": user_state.difficulty,
                "explanation": state.lesson_markdown,
                "example": f"Practice problems on {self.concepts.label(concept)}.",
                "has_pdf": False,
                "sources": [],
            }

        state.problem_index = 0
        state.problems_correct = 0
        state.last_evaluation = None
        state.phase = "lesson"
        state.error_message = ""

        self.session_log.log(
            config.user_id, state.topic, "lesson",
            concept=concept,
            payload={"has_pdf": state.lesson_has_pdf, "ui": "panel"},
        )
        return state

    def begin_problems(self, state: LearningPanelState) -> LearningPanelState:
        """Move from lesson view to first problem."""
        state = self._load_problem(state)
        state.phase = "problem"
        return state

    def _load_problem(self, state: LearningPanelState) -> LearningPanelState:
        config = state.config
        assert config is not None
        concept = self._current_concept(state)
        diff = DIFFICULTY_SEQUENCE[
            min(state.problem_index, len(DIFFICULTY_SEQUENCE) - 1)
        ]
        state.current_difficulty = diff

        user_state = self.progression.build_user_state(config.user_id, state.topic)
        user_state.current_concept = concept
        user_state.difficulty = diff

        try:
            state.current_problem = generate_problem(user_state, concept)
        except Exception as exc:
            logger.exception("problem_gen")
            state.error_message = f"Could not generate problem: {exc}"
            state.current_problem = None

        state.last_evaluation = None
        return state

    def submit_answer(
        self, state: LearningPanelState, answer: str
    ) -> LearningPanelState:
        """Evaluate learner answer and switch to feedback phase."""
        config = state.config
        problem = state.current_problem
        if not config or not problem:
            state.error_message = "No active problem."
            return state

        trimmed = answer.strip()
        if not trimmed:
            state.error_message = "Please enter an answer before submitting."
            return state

        concept = self._current_concept(state)
        try:
            result = self.evaluator.evaluate_and_update(
                config.user_id,
                state.topic,
                concept,
                trimmed,
                problem.expected_answer,
                difficulty=state.current_difficulty,
                question=problem.question,
            )
        except Exception as exc:
            logger.exception("evaluate")
            state.error_message = f"Evaluation failed: {exc}"
            return state

        state.last_evaluation = PanelEvaluationView.from_result(result)
        state.error_message = ""
        if result.correct:
            state.problems_correct += 1

        self.session_log.log(
            config.user_id, state.topic, "answer",
            concept=concept,
            payload={
                "correct": result.correct,
                "score": result.score,
                "ui": "panel",
            },
        )
        state.phase = "feedback"
        return state

    def next_problem(self, state: LearningPanelState) -> LearningPanelState:
        """Advance to next problem or finish the concept."""
        config = state.config
        assert config is not None

        state.problem_index += 1
        if state.problem_index < config.problems_per_concept:
            state = self._load_problem(state)
            state.phase = "problem"
            return state

        return self._finish_concept(state)

    def _finish_concept(self, state: LearningPanelState) -> LearningPanelState:
        config = state.config
        assert config is not None
        concept = self._current_concept(state)

        record = self.memory.get_concept_progress(
            config.user_id, state.topic, concept
        )
        if state.last_evaluation and state.last_evaluation.progression_action:
            action = state.last_evaluation.progression_action
        else:
            action = self.progression.decide_next_step(
                config.user_id, concept, state.topic
            ).action

        state.concept_progression_action = action
        state.phase = "concept_summary"
        return state

    def continue_after_concept(
        self, state: LearningPanelState
    ) -> LearningPanelState:
        """Apply progression and load next concept or end session."""
        config = state.config
        assert config is not None
        action = state.concept_progression_action

        if action == "advance":
            state.concept_index += 1
        elif action in ("reteach", "repeat"):
            pass
        elif action == "review_previous":
            if state.concept_index > 0:
                state.concept_index -= 1
            else:
                state.concept_index += 1
        else:
            state.concept_index += 1

        if state.concept_index >= len(state.concepts):
            state.phase = "done"
            self.session_log.log(
                config.user_id, state.topic, "session_end",
                payload={"ui": "panel"},
            )
            return state

        return self._load_lesson(state)

    def progress_summary(self, state: LearningPanelState) -> list[dict]:
        """Rows for sidebar progress table."""
        config = state.config
        if not config:
            return []
        rows = []
        for p in self.memory.get_user_progress(config.user_id, state.topic):
            rows.append(
                {
                    "concept": self.concepts.label(p.concept),
                    "confidence": p.confidence_score,
                    "attempts": p.attempts,
                    "correct": p.correct_count,
                }
            )
        return rows
