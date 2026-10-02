"""API service layer wrapping LearningPanelController."""

from __future__ import annotations

from config import CONFIDENCE_PRACTICE
from app.learning_loop import SessionConfig
from app.panel_controller import LearningPanelController, LearningPanelState
from api.lesson_serializer import lesson_to_api
from api.schemas import (
    ConceptProgressItem,
    FeedbackResponse,
    LessonResponse,
    ProblemResponse,
    SessionSnapshot,
    StartTopicRequest,
)
from api import session_store
from generation.lesson import generate_lesson


_controller = LearningPanelController()


def _concept_progress(
    state: LearningPanelState, weak_threshold: float = CONFIDENCE_PRACTICE
) -> list[ConceptProgressItem]:
    config = state.config
    if not config:
        return []
    current = (
        state.concepts[state.concept_index]
        if state.concepts and state.concept_index < len(state.concepts)
        else ""
    )
    progress_map = {
        p.concept: p
        for p in _controller.memory.get_user_progress(config.user_id, state.topic)
    }
    weak_ids = {
        p.concept
        for p in _controller.memory.get_weak_areas(config.user_id, state.topic)
    }

    items: list[ConceptProgressItem] = []
    for cid in state.concepts:
        record = progress_map.get(cid)
        items.append(
            ConceptProgressItem(
                concept_id=cid,
                label=_controller.concepts.label(cid),
                confidence=record.confidence_score if record else 0.0,
                attempts=record.attempts if record else 0,
                correct=record.correct_count if record else 0,
                is_current=cid == current,
                is_weak=cid in weak_ids,
            )
        )
    return items


def _lesson_response(state: LearningPanelState) -> LessonResponse | None:
    payload = state.lesson_payload
    if payload:
        return LessonResponse(**payload)
    return None


def _problem_response(state: LearningPanelState) -> ProblemResponse | None:
    problem = state.current_problem
    config = state.config
    if not problem or not config:
        return None
    return ProblemResponse(
        problem_id=problem.problem_id,
        concept=problem.concept,
        question=problem.question,
        difficulty=state.current_difficulty,
        hint=problem.hint,
        index=state.problem_index + 1,
        total=config.problems_per_concept,
    )


def _feedback_response(state: LearningPanelState) -> FeedbackResponse | None:
    ev = state.last_evaluation
    if not ev:
        return None
    return FeedbackResponse(
        correct=ev.correct,
        score=ev.score,
        mistake_type=ev.mistake_type,
        feedback=ev.feedback,
        hint=ev.hint,
        confidence=ev.confidence,
        confidence_delta=ev.confidence_delta,
        progression_action=ev.progression_action,
        progression_message=ev.progression_message,
    )


def snapshot(session_id: str, state: LearningPanelState) -> SessionSnapshot:
    config = state.config
    current_id = ""
    current_label = ""
    if state.concepts and state.concept_index < len(state.concepts):
        current_id = state.concepts[state.concept_index]
        current_label = _controller.concepts.label(current_id)

    return SessionSnapshot(
        session_id=session_id,
        phase=state.phase,
        topic=state.topic,
        user_id=config.user_id if config else "",
        level=config.level if config else "beginner",
        current_concept_id=current_id,
        current_concept_label=current_label,
        concept_index=state.concept_index,
        total_concepts=len(state.concepts),
        problem_index=state.problem_index,
        problems_per_concept=config.problems_per_concept if config else 3,
        problems_correct=state.problems_correct,
        rag_available=state.rag_available,
        progression_action=state.concept_progression_action,
        concepts=_concept_progress(state),
        lesson=_lesson_response(state),
        problem=_problem_response(state),
        feedback=_feedback_response(state),
        error=state.error_message or None,
    )


def _save_lesson_payload(state: LearningPanelState) -> LearningPanelState:
    """Regenerate structured lesson payload for API consumers."""
    config = state.config
    if not config or not state.concepts:
        return state
    concept = state.concepts[state.concept_index]
    user_state = _controller.progression.build_user_state(config.user_id, state.topic)
    user_state.current_concept = concept
    user_state.focus_concepts = list(
        dict.fromkeys([concept, *user_state.weak_concepts])
    )
    try:
        lesson = generate_lesson(user_state)
        state.lesson_payload = lesson_to_api(lesson, _controller.concepts)
        state.lesson_markdown = lesson.render()
        state.lesson_has_pdf = lesson.has_pdf_content
    except FileNotFoundError:
        label = _controller.concepts.label(concept)
        state.lesson_payload = {
            "concept_id": concept,
            "concept_label": label,
            "title": label,
            "topic": state.topic,
            "difficulty": user_state.difficulty,
            "explanation": (
                f"Study {label} at {user_state.difficulty} level. "
                "Ingest PDFs for richer content."
            ),
            "example": f"Try a practice problem on {label}.",
            "has_pdf": False,
            "sources": [],
            "markdown": state.lesson_markdown,
        }
    return state


def start_topic(req: StartTopicRequest) -> tuple[str, SessionSnapshot]:
    config = SessionConfig(
        user_id=req.user_id,
        topic=req.topic,
        level=req.level,
        problems_per_concept=req.problems_per_concept,
        max_concepts=req.max_concepts,
    )
    state = _controller.start_session(config)
    if state.error_message:
        session_id = session_store.create_session(state)
        return session_id, snapshot(session_id, state)
    state = _save_lesson_payload(state)
    session_id = session_store.create_session(state)
    return session_id, snapshot(session_id, state)


def get_session_state(session_id: str) -> SessionSnapshot:
    state = session_store.get_session(session_id)
    if not state:
        raise KeyError("Session not found")
    return snapshot(session_id, state)


def get_lesson(session_id: str) -> SessionSnapshot:
    state = session_store.get_session(session_id)
    if not state:
        raise KeyError("Session not found")
    state = _save_lesson_payload(state)
    session_store.update_session(session_id, state)
    return snapshot(session_id, state)


def begin_problems(session_id: str) -> SessionSnapshot:
    state = session_store.get_session(session_id)
    if not state:
        raise KeyError("Session not found")
    state = _controller.begin_problems(state)
    session_store.update_session(session_id, state)
    return snapshot(session_id, state)


def get_problem(session_id: str) -> SessionSnapshot:
    state = session_store.get_session(session_id)
    if not state:
        raise KeyError("Session not found")
    if state.phase == "lesson":
        state = _controller.begin_problems(state)
    elif state.phase in ("feedback", "concept_summary"):
        raise ValueError("Call /next_step before requesting the next problem.")
    elif state.phase == "problem" and not state.current_problem:
        state = _controller._load_problem(state)
    session_store.update_session(session_id, state)
    return snapshot(session_id, state)


def submit_answer(session_id: str, answer: str) -> SessionSnapshot:
    state = session_store.get_session(session_id)
    if not state:
        raise KeyError("Session not found")
    state = _controller.submit_answer(state, answer)
    session_store.update_session(session_id, state)
    return snapshot(session_id, state)


def next_step(session_id: str) -> SessionSnapshot:
    state = session_store.get_session(session_id)
    if not state:
        raise KeyError("Session not found")

    if state.phase == "lesson":
        state = _controller.begin_problems(state)
    elif state.phase == "feedback":
        state = _controller.next_problem(state)
    elif state.phase == "concept_summary":
        state = _controller.continue_after_concept(state)
        if state.phase == "lesson":
            state = _save_lesson_payload(state)
    elif state.phase == "done":
        pass
    else:
        state = _controller.next_problem(state)

    session_store.update_session(session_id, state)
    return snapshot(session_id, state)
