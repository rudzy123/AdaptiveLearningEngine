"""Adaptive Learning Engine: the demo UI (Streamlit).

    python -m ale ui

The UI holds no learner state of its own. Every screen is rebuilt from `Tutor.state()` and
`Tutor.progress()`, which read SQLite, so a browser refresh or a new server process shows the same
lesson, problem, evaluation and confidence. The learner id lives in the URL (?user=...).
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # allow `streamlit run ale/interfaces/ui.py` without installing
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from ale.engine.config import default_db_path  # noqa: E402
from ale.engine.errors import TutorError  # noqa: E402
from ale.engine.tutor import USER_ID_RE, Tutor  # noqa: E402

TAGLINE = "Building intelligent systems that adapt to human learning."
CLAIMS = [
    "dynamic adaptive learning loop",
    "5-layer evaluation engine",
    "confidence-based progression",
    "local RAG pipeline (no external APIs)",
    "persistent learner state",
]
ACTION_COLORS = {
    "advance": "#4ade80",
    "practice_harder": "#fbbf24",
    "repeat": "#6ea8fe",
    "reteach": "#f87171",
}
LAYER_TITLES = {
    "exact_match": "exact / numeric match",
    "partial_credit": "partial credit",
    "reasoning_alignment": "reasoning alignment",
    "error_typing": "error typing",
    "confidence_delta": "confidence delta",
}

CSS = """
<style>
.block-container { padding-top: 2rem; max-width: 1100px; }
h1, h2, h3 { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: -0.01em; }
.ale-title { font-size: 1.9rem; font-weight: 600; margin: 0; }
.ale-tag { color: #8b95a1; margin: .15rem 0 .8rem 0; }
.ale-pill { display: inline-block; border: 1px solid #2a323c; color: #9aa6b2; border-radius: 3px;
            padding: 1px 8px; margin: 0 6px 6px 0; font-size: .72rem; }
.ale-label { color: #6ea8fe; font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; margin: 1.4rem 0 .3rem 0; }
.ale-meta { color: #8b95a1; font-size: .8rem; }
.ale-table { width: 100%; border-collapse: collapse; font-size: .82rem; }
.ale-table th { text-align: left; color: #8b95a1; font-weight: 400; border-bottom: 1px solid #2a323c; padding: 4px 8px; }
.ale-table td { border-bottom: 1px solid #1a2028; padding: 5px 8px; vertical-align: top; }
.ale-action { display: inline-block; border: 1px solid; border-radius: 3px; padding: 4px 14px;
              font-weight: 600; letter-spacing: .08em; text-transform: uppercase; }
.ale-kv { display: flex; gap: 10px; flex-wrap: wrap; margin: 12px 0; }
.ale-kv > div { border: 1px solid #2a323c; border-radius: 3px; padding: 6px 12px; min-width: 150px; flex: 1; }
.ale-kv .k { color: #8b95a1; font-size: .68rem; text-transform: uppercase; letter-spacing: .08em; }
.ale-kv .v { font-size: 1.05rem; margin-top: 2px; }
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu { display: none; }
.ale-cite { border-left: 2px solid #2a323c; padding: 2px 10px; margin: 4px 0; font-size: .8rem; color: #9aa6b2; }
</style>
"""


@st.cache_resource(show_spinner=False)
def get_tutor(db: str) -> Tutor:
    return Tutor(db)


def esc(x: object) -> str:
    return html.escape(str(x))


def label(text: str) -> None:
    st.markdown(f'<div class="ale-label">{esc(text)}</div>', unsafe_allow_html=True)


def render_header() -> None:
    st.markdown('<p class="ale-title">Adaptive Learning Engine</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="ale-tag">{esc(TAGLINE)}</p>', unsafe_allow_html=True)
    st.markdown("".join(f'<span class="ale-pill">{esc(c)}</span>' for c in CLAIMS), unsafe_allow_html=True)


def render_sidebar(tutor: Tutor, db: str) -> tuple[str, dict | None]:
    sb = st.sidebar
    sb.markdown("### Learner")
    default_user = st.query_params.get("user", "")
    user = sb.text_input("Learner id", value=default_user, placeholder="e.g. ada", max_chars=64).strip()
    if user and not USER_ID_RE.match(user):
        sb.error("Learner id may use letters, digits, '_', '.' and '-' only.")
        user = ""
    if user and user != default_user:
        st.query_params["user"] = user
    state = None
    if user:
        try:
            state = tutor.state(user)
        except TutorError as exc:
            if exc.code != "no_session":
                sb.error(exc.message)

    topics = tutor.topics()
    titles = {t["title"]: t["id"] for t in topics}
    current = state["topic_title"] if state else next(iter(titles))
    choice = sb.selectbox("Topic", list(titles), index=list(titles).index(current))
    c1, c2 = sb.columns(2)
    if c1.button("Start / resume", disabled=not user, use_container_width=True):
        try:
            tutor.start_topic(user, titles[choice])
            st.rerun()
        except TutorError as exc:
            sb.error(exc.message)
    if c2.button("Restart", disabled=not user, use_container_width=True):
        try:
            tutor.start_topic(user, titles[choice], restart=True)
            st.rerun()
        except TutorError as exc:
            sb.error(exc.message)

    if user:
        sb.markdown("### Confidence by concept")
        progress = tutor.progress(user)
        for c in progress["concepts"]:
            marker = "  (current)" if c["current"] else ""
            sb.markdown(
                f'<div class="ale-meta">{esc(c["title"])}{marker} &nbsp; {c["confidence"]:.0%}'
                f' &middot; {c["attempts"]} attempts</div>',
                unsafe_allow_html=True,
            )
            sb.progress(min(1.0, c["confidence"]))
    sb.markdown("---")
    sb.caption(
        f"Local RAG over {tutor.store.chunk_count()} chunks. No external APIs, no keys. "
        f"Learner state: SQLite at `{db}`. Refresh the page: the state stays."
    )
    return user, state


def render_lesson(state: dict) -> None:
    lesson = state["lesson"]
    label("1. Lesson, grounded in retrieved sources")
    if not lesson:
        st.markdown('<span class="ale-meta">The next lesson is generated when you continue.</span>', unsafe_allow_html=True)
        return
    st.markdown(f"**{lesson['title']}**")
    st.markdown(f'<span class="ale-meta">{esc(lesson["adaptation_note"])}</span>', unsafe_allow_html=True)
    st.markdown(lesson["body"])
    if lesson["key_points"]:
        st.markdown("**Key points** (extracted from the sources)")
        for kp in lesson["key_points"]:
            st.markdown(f"- {kp}")
    st.markdown("**Sources**")
    for c in lesson["citations"]:
        st.markdown(
            f'<div class="ale-cite">[{c["n"]}] {esc(c["source"])} &middot; {esc(c["section"])} &middot; '
            f'chunk <code>{esc(c["chunk_id"])}</code> &middot; BM25 score {c["score"]}</div>',
            unsafe_allow_html=True,
        )
    st.caption(f"Generated by: {lesson['generator']}; retrieval: {lesson['retrieval']['engine']}")


def render_problem(tutor: Tutor, user: str, state: dict) -> None:
    label("2. Practice problem")
    problem = state["problem"]
    if problem:
        st.markdown(
            f'<span class="ale-meta">{esc(state["concept_title"])} &middot; difficulty {problem["difficulty"]} of 3'
            f' &middot; {esc(problem["bank_id"])}</span>',
            unsafe_allow_html=True,
        )
        st.markdown(f"**{problem['prompt']}**")
        with st.form("answer_form", clear_on_submit=True):
            answer = st.text_input("Answer", help=problem["format"], placeholder=problem["format"])
            reasoning = st.text_area("Reasoning (optional)", height=80,
                                     placeholder="Explain your steps; reasoning alignment is scored separately.")
            submitted = st.form_submit_button("Submit answer")
        if submitted:
            if not answer.strip():
                st.warning("Enter an answer first.")
            else:
                try:
                    tutor.submit_answer(user, problem["problem_id"], answer, reasoning)
                    st.rerun()
                except TutorError as exc:
                    st.error(exc.message)
        return
    if state["status"] == "completed":
        st.success(f"Topic complete: {state['topic_title']}. Restart it from the sidebar to practice again.")
        return
    started = state["last_result"] is not None
    if st.button("Continue" if started else "Load lesson and problem", type="primary"):
        try:
            tutor.get_lesson(user)
            tutor.get_problem(user)
            st.rerun()
        except TutorError as exc:
            st.error(exc.message)


def render_result(state: dict) -> None:
    r = state["last_result"]
    if not r:
        return
    label("3. Evaluation, five layers")
    st.markdown(f"**{r['prompt']}**")
    st.markdown(f'<span class="ale-meta">Your answer: {esc(r["answer"])}'
                + (f' &middot; reasoning: {esc(r["reasoning"])}' if r["reasoning"] else "") + "</span>",
                unsafe_allow_html=True)
    rows = []
    for layer in r["evaluation"]["layers"]:
        name = layer["name"]
        if name == "error_typing":
            value = layer["error_type"].replace("_", " ")
        elif name == "confidence_delta":
            value = f'{layer["before"]:.2f} &rarr; {layer["after"]:.2f} ({layer["delta"]:+.2f})'
        else:
            value = f'{layer["score"]:.2f}'
        rows.append(
            f'<tr><td>L{layer["layer"]}</td><td>{esc(LAYER_TITLES[name])}</td><td>{value}</td>'
            f'<td>{esc(layer["detail"])}</td></tr>'
        )
    st.markdown(
        '<table class="ale-table"><tr><th></th><th>layer</th><th>result</th><th>detail</th></tr>'
        + "".join(rows) + "</table>",
        unsafe_allow_html=True,
    )
    m, sig = r["memory"], r["learning_signal"]
    cards = [
        ("score", f"{r['score']:.2f} ({'correct' if r['correct'] else 'not yet'})"),
        ("error type", r["error_type"].replace("_", " ")),
        ("confidence", f"{m['confidence_before']:.0%} &rarr; {m['confidence_after']:.0%} ({m['delta']:+.0%})"),
        ("weak concept / retry", f"{'yes' if sig['weak_concept'] else 'no'} / {'yes' if sig['retry_recommended'] else 'no'}"),
    ]
    st.markdown(
        '<div class="ale-kv">' + "".join(f'<div><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in cards)
        + "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"{r['evaluation']['feedback']}")
    if not r["correct"] and r["evaluation"]["hint"]:
        st.markdown(f"Hint: {r['evaluation']['hint']}")
        st.markdown(f"Worked solution: {r['evaluation']['explanation']}")

    nxt = r["next_step"]
    color = ACTION_COLORS[nxt["action"]]
    label("4. Next step, chosen from confidence and error type")
    st.markdown(
        f'<span class="ale-action" style="color:{color};border-color:{color}">{esc(nxt["label"])}</span>'
        f'&nbsp; <span class="ale-meta">rule: {esc(nxt["rule"])} &middot; next: {esc(nxt["next_concept_title"])}'
        f' &middot; difficulty {nxt["difficulty"]} &middot; lesson level {esc(nxt["lesson_level"])}</span>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<span class="ale-meta">{esc(nxt["reason"])}</span>', unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="Adaptive Learning Engine", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    db = str(default_db_path())
    tutor = get_tutor(db)
    render_header()
    user, state = render_sidebar(tutor, db)
    if not user:
        st.info("Enter a learner id in the sidebar, choose a topic, then Start / resume.")
        return
    if state is None:
        st.info(f"No session yet for '{user}'. Choose a topic and press Start / resume.")
        return
    st.markdown(
        f'<span class="ale-meta">topic: {esc(state["topic_title"])} &middot; concept: {esc(state["concept_title"])}'
        f' &middot; difficulty {state["difficulty"]} &middot; lesson level: {esc(state["lesson_level"])}'
        f' &middot; phase: {esc(state["phase"])}</span>',
        unsafe_allow_html=True,
    )
    render_lesson(state)
    render_problem(tutor, user, state)
    render_result(state)


main()
