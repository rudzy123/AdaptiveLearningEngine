"""Progress dashboard: confidence visualization, refreshes after each evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

from config import CONFIDENCE_MASTERED, CONFIDENCE_PRACTICE
from engine.concepts import ConceptRegistry
from engine.memory import MemoryStore, UserProgress
from app.panel_controller import PanelEvaluationView

# Threshold bands for chart coloring
MASTERED = CONFIDENCE_MASTERED
PRACTICE = CONFIDENCE_PRACTICE


@dataclass
class ConceptConfidenceRow:
    """One concept row for bar charts."""

    concept_id: str
    label: str
    confidence: float
    attempts: int
    correct: int
    status: str  # weak | building | strong | not_started
    is_current: bool = False


@dataclass
class ProgressDashboardData:
    """Aggregated metrics and series for charts."""

    user_id: str
    topic: str
    rows: list[ConceptConfidenceRow] = field(default_factory=list)
    timeline: list[dict] = field(default_factory=list)
    average_confidence: float = 0.0
    mastered_count: int = 0
    weak_count: int = 0
    total_attempts: int = 0
    refresh_token: int = 0


def _status_for(confidence: float, attempts: int) -> str:
    if attempts == 0:
        return "not_started"
    if confidence >= MASTERED:
        return "strong"
    if confidence >= PRACTICE:
        return "building"
    return "weak"


def load_dashboard_data(
    memory: MemoryStore,
    user_id: str,
    topic: str,
    *,
    concepts: ConceptRegistry | None = None,
    curriculum_concepts: list[str] | None = None,
    highlight_concept: str | None = None,
    refresh_token: int = 0,
) -> ProgressDashboardData:
    """Load current confidence and history from memory store."""
    registry = concepts or ConceptRegistry()
    progress = memory.get_user_progress(user_id, topic)
    progress_by_id = {p.concept: p for p in progress}

    ordered_ids = curriculum_concepts or registry.get_concepts_for_topic(topic)
    seen = set(ordered_ids)
    for p in progress:
        if p.concept not in seen:
            ordered_ids.append(p.concept)
            seen.add(p.concept)

    rows: list[ConceptConfidenceRow] = []
    confidences: list[float] = []
    mastered = 0
    weak = 0
    total_attempts = 0

    for concept_id in ordered_ids:
        record = progress_by_id.get(concept_id)
        if record:
            conf = record.confidence_score
            attempts = record.attempts
            correct = record.correct_count
        else:
            conf = 0.0
            attempts = 0
            correct = 0

        status = _status_for(conf, attempts)
        if status == "strong":
            mastered += 1
        elif status == "weak":
            weak += 1
        if attempts > 0:
            confidences.append(conf)
        total_attempts += attempts

        rows.append(
            ConceptConfidenceRow(
                concept_id=concept_id,
                label=registry.label(concept_id),
                confidence=conf,
                attempts=attempts,
                correct=correct,
                status=status,
                is_current=concept_id == highlight_concept,
            )
        )

    timeline = memory.get_confidence_timeline(user_id, topic)
    avg = sum(confidences) / len(confidences) if confidences else 0.0

    return ProgressDashboardData(
        user_id=user_id,
        topic=topic,
        rows=rows,
        timeline=timeline,
        average_confidence=avg,
        mastered_count=mastered,
        weak_count=weak,
        total_attempts=total_attempts,
        refresh_token=refresh_token,
    )


def _confidence_bar_df(rows: list[ConceptConfidenceRow]) -> pd.DataFrame:
    """DataFrame for horizontal confidence bars."""
    records = []
    for row in rows:
        if row.attempts == 0 and not row.is_current:
            continue
        records.append(
            {
                "Concept": row.label + (" ★" if row.is_current else ""),
                "Confidence": row.confidence,
                "Attempts": row.attempts,
            }
        )
    if not records:
        for row in rows[:8]:
            records.append(
                {
                    "Concept": row.label + (" ★" if row.is_current else ""),
                    "Confidence": row.confidence,
                    "Attempts": row.attempts,
                }
            )
    return pd.DataFrame(records)


def _timeline_df(timeline: list[dict], focus_concept: str | None) -> pd.DataFrame:
    if not timeline:
        return pd.DataFrame(columns=["Step", "Confidence", "Concept"])

    df = pd.DataFrame(timeline)
    df["Step"] = range(1, len(df) + 1)
    if focus_concept:
        df = df[df["concept"] == focus_concept]
    if df.empty:
        df = pd.DataFrame(timeline)
        df["Step"] = range(1, len(df) + 1)
    return df.rename(columns={"confidence": "Confidence", "concept": "Concept"})


def render_progress_dashboard(
    data: ProgressDashboardData,
    *,
    last_evaluation: PanelEvaluationView | None = None,
    compact: bool = False,
) -> None:
    """
    Render confidence charts and metrics.

    Call after each evaluation; parent should st.rerun() so charts reflect new DB state.
    """
    st.markdown("### Progress dashboard")
    if last_evaluation:
        delta_color = "normal" if last_evaluation.confidence_delta >= 0 else "inverse"
        st.caption(
            f"Updated after latest answer · "
            f"{'✓' if last_evaluation.correct else '✗'} "
            f"{last_evaluation.mistake_type}"
        )
        st.metric(
            "Latest concept confidence",
            f"{last_evaluation.confidence:.0%}",
            delta=f"{last_evaluation.confidence_delta:+.2f}",
            delta_color=delta_color,
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Avg confidence", f"{data.average_confidence:.0%}")
    c2.metric("Mastered", data.mastered_count)
    c3.metric("Needs practice", data.weak_count)
    c4.metric("Total attempts", data.total_attempts)

    bar_df = _confidence_bar_df(data.rows)
    if not bar_df.empty:
        st.markdown("**Confidence by concept**")
        chart_df = bar_df.set_index("Concept")[["Confidence"]]
        st.bar_chart(
            chart_df,
            height=280 if not compact else 200,
            color="#3b82f6",
        )
        if not compact:
            st.caption(
                f"Green zone ≥ {MASTERED:.0%} mastered · "
                f"Amber ≥ {PRACTICE:.0%} building · Below {PRACTICE:.0%} needs work · ★ current"
            )
    else:
        st.info("Answer a problem to see confidence scores here.")

    focus = None
    for row in data.rows:
        if row.is_current:
            focus = row.concept_id
            break

    if data.timeline:
        st.markdown("**Confidence over time**")
        line_df = _timeline_df(data.timeline, focus)
        if len(line_df) > 1:
            st.line_chart(
                line_df.set_index("Step")[["Confidence"]],
                height=220 if not compact else 160,
                color="#10b981",
            )
            if focus:
                st.caption(f"Timeline filtered to current concept: `{focus}`")
        else:
            st.caption("More answers needed to show a trend line.")

    with st.expander("Concept details", expanded=False):
        detail = pd.DataFrame(
            [
                {
                    "Concept": r.label,
                    "Confidence": f"{r.confidence:.0%}",
                    "Attempts": r.attempts,
                    "Correct": r.correct,
                    "Status": r.status,
                    "Current": "★" if r.is_current else "",
                }
                for r in data.rows
                if r.attempts > 0 or r.is_current
            ]
        )
        if detail.empty:
            st.write("No attempts recorded yet.")
        else:
            st.dataframe(detail, use_container_width=True, hide_index=True)


def render_sidebar_mini_dashboard(data: ProgressDashboardData) -> None:
    """Compact confidence bars for the sidebar."""
    st.sidebar.markdown("### Confidence")
    for row in data.rows:
        if row.attempts == 0 and not row.is_current:
            continue
        label = row.label[:18] + (" ★" if row.is_current else "")
        st.sidebar.progress(
            min(1.0, max(0.0, row.confidence)),
            text=f"{label} ({row.confidence:.0%})",
        )
