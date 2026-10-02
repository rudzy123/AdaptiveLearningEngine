#!/usr/bin/env python3
"""
Main learning panel — Streamlit UI.

Run from adaptive_learning_engine/:
    streamlit run app/learning_panel.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st  # noqa: E402

from app.learning_loop import SessionConfig  # noqa: E402
from app.panel_controller import (  # noqa: E402
    LearningPanelController,
    LearningPanelState,
    PanelEvaluationView,
)
from app.progress_dashboard import (  # noqa: E402
    load_dashboard_data,
    render_progress_dashboard,
    render_sidebar_mini_dashboard,
)

TOPIC_OPTIONS = {
    "Math (Linear Algebra)": "math",
    "Physics": "physics",
    "Computer Science (Algorithms)": "cs",
}

LEVEL_OPTIONS = ["beginner", "intermediate", "advanced"]


def init_session() -> None:
    if "panel_state" not in st.session_state:
        st.session_state.panel_state = LearningPanelState()
    if "controller" not in st.session_state:
        st.session_state.controller = LearningPanelController()
    if "dashboard_refresh" not in st.session_state:
        st.session_state.dashboard_refresh = 0


def get_dashboard_data(
    state: LearningPanelState, controller: LearningPanelController
):
    """Load dashboard metrics from memory (fresh after each evaluation)."""
    config = state.config
    if not config or not state.topic:
        return None
    highlight = None
    if state.concepts and state.concept_index < len(state.concepts):
        highlight = state.concepts[state.concept_index]
    return load_dashboard_data(
        controller.memory,
        config.user_id,
        state.topic,
        curriculum_concepts=state.concepts or None,
        highlight_concept=highlight,
        refresh_token=st.session_state.dashboard_refresh,
    )


def render_sidebar(state: LearningPanelState, controller: LearningPanelController) -> None:
    st.sidebar.header("Session")
    user_id = st.sidebar.text_input("User ID", value="default")
    topic_label = st.sidebar.selectbox(
        "Topic", list(TOPIC_OPTIONS.keys()), index=0
    )
    level = st.sidebar.selectbox("Level", LEVEL_OPTIONS, index=0)
    problems = st.sidebar.slider("Problems per concept", 1, 5, 3)
    max_concepts = st.sidebar.slider("Max concepts", 1, 10, 5)

    if state.phase == "setup":
        if st.sidebar.button("Start learning session", type="primary", use_container_width=True):
            config = SessionConfig(
                user_id=user_id.strip() or "default",
                topic=TOPIC_OPTIONS[topic_label],
                level=level,  # type: ignore[arg-type]
                problems_per_concept=problems,
                max_concepts=max_concepts,
            )
            st.session_state.panel_state = controller.start_session(config)
            st.rerun()

    if state.phase != "setup":
        concept = (
            state.concepts[state.concept_index]
            if state.concepts
            else "—"
        )
        st.sidebar.markdown(
            f"**Topic:** `{state.topic}`  \n"
            f"**Concept:** `{concept}` ({state.concept_index + 1}/{len(state.concepts)})  \n"
            f"**Problem:** {min(state.problem_index + 1, state.config.problems_per_concept if state.config else 0)}"
            f"/{state.config.problems_per_concept if state.config else 0}"
        )
        if not state.rag_available:
            st.sidebar.warning("PDF chunks not found — limited lesson context.")

        dash = get_dashboard_data(state, controller)
        if dash:
            render_sidebar_mini_dashboard(dash)

        if st.sidebar.button("Reset session", use_container_width=True):
            st.session_state.panel_state = LearningPanelState()
            st.rerun()


def render_lesson(state: LearningPanelState) -> None:
    st.subheader("Lesson")
    if state.lesson_has_pdf:
        st.caption("Includes excerpts from your ingested course PDFs.")
    else:
        st.caption("Template lesson — run ingest for PDF-backed content.")
    st.markdown(state.lesson_markdown or "_No lesson loaded._")


def render_problem(state: LearningPanelState) -> None:
    problem = state.current_problem
    if not problem:
        if state.error_message:
            st.error(state.error_message)
        return

    st.subheader("Problem")
    st.markdown(
        f"**{state.problem_index + 1}** · `{state.current_difficulty}` · "
        f"`{problem.concept}`"
    )
    st.info(problem.question)


def render_answer_input(
    state: LearningPanelState, controller: LearningPanelController
) -> None:
    st.subheader("Your answer")
    key = f"answer_{state.concept_index}_{state.problem_index}"
    answer = st.text_area(
        "Type your answer",
        height=100,
        key=key,
        placeholder="Enter your solution or explanation…",
    )
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Submit answer", type="primary", use_container_width=True):
            st.session_state.panel_state = controller.submit_answer(state, answer)
            st.session_state.dashboard_refresh += 1
            st.rerun()
    with col2:
        if problem := state.current_problem:
            if problem.hint and st.button("Show hint"):
                st.session_state.show_hint = problem.hint
                st.rerun()
    if st.session_state.get("show_hint") and state.current_problem:
        st.warning(f"Hint: {st.session_state.show_hint}")


def render_evaluation(feedback: PanelEvaluationView) -> None:
    st.subheader("Evaluation")
    if feedback.correct:
        st.success(f"Correct · Score {feedback.score:.0%}")
    else:
        st.error(f"Incorrect · Score {feedback.score:.0%}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Confidence", f"{feedback.confidence:.0%}")
    c2.metric("Δ confidence", f"{feedback.confidence_delta:+.2f}")
    c3.metric("Error type", feedback.mistake_type or "none")

    st.markdown("**Feedback**")
    st.write(feedback.feedback)
    if feedback.hint:
        st.markdown("**Hint**")
        st.info(feedback.hint)
    if feedback.progression_message:
        st.markdown("**Next step**")
        st.write(
            f"`{feedback.progression_action}` — {feedback.progression_message}"
        )


def render_concept_summary(
    state: LearningPanelState, controller: LearningPanelController
) -> None:
    st.subheader("Concept complete")
    total = state.config.problems_per_concept if state.config else 0
    st.write(
        f"You answered **{state.problems_correct}/{total}** correctly on "
        f"**{state.concepts[state.concept_index]}**."
    )
    st.info(f"Progression: **{state.concept_progression_action}**")
    if st.button("Continue", type="primary"):
        st.session_state.panel_state = controller.continue_after_concept(state)
        st.session_state.pop("show_hint", None)
        st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="Adaptive Learning Panel",
        page_icon="📚",
        layout="wide",
    )
    init_session()
    state: LearningPanelState = st.session_state.panel_state
    controller: LearningPanelController = st.session_state.controller

    st.title("Adaptive Learning Panel")
    st.caption("Lesson · one problem at a time · evaluate · progress")

    if state.phase == "setup":
        st.markdown(
            "Configure your session in the **sidebar**, then click "
            "**Start learning session**."
        )
        render_sidebar(state, controller)
        return

    render_sidebar(state, controller)

    dash_data = get_dashboard_data(state, controller)
    last_eval = state.last_evaluation if state.phase == "feedback" else None

    main_col, dash_col = st.columns([1.55, 1], gap="medium")

    with dash_col:
        with st.container(border=True):
            if dash_data:
                render_progress_dashboard(
                    dash_data,
                    last_evaluation=last_eval,
                    compact=state.phase == "problem",
                )
            else:
                st.info("Start a session to track confidence.")

    with main_col:
        if state.error_message and state.phase not in ("feedback",):
            st.warning(state.error_message)

        with st.container(border=True):
            render_lesson(state)

        if state.phase == "lesson":
            if st.button("Start problems for this concept", type="primary"):
                st.session_state.panel_state = controller.begin_problems(state)
                st.rerun()
            return

        if state.phase in ("problem", "feedback"):
            with st.container(border=True):
                render_problem(state)

            if state.phase == "problem":
                with st.container(border=True):
                    render_answer_input(state, controller)
            elif state.last_evaluation:
                with st.container(border=True):
                    render_evaluation(state.last_evaluation)
                if st.button("Next problem →", type="primary"):
                    st.session_state.panel_state = controller.next_problem(state)
                    st.session_state.pop("show_hint", None)
                    st.rerun()

        elif state.phase == "concept_summary":
            render_concept_summary(state, controller)

        elif state.phase == "done":
            st.balloons()
            st.success("Session complete!")
            if st.button("Start a new session"):
                st.session_state.panel_state = LearningPanelState()
                st.session_state.dashboard_refresh = 0
                st.rerun()


if __name__ == "__main__":
    main()
