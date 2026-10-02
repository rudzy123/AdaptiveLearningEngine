"""Command line interface: demo, serve, ui, ingest, progress, simulate."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from ale import __version__
from ale.engine.config import default_db_path
from ale.engine.errors import TutorError
from ale.engine.ingest import ingest_path
from ale.engine.tutor import Tutor

RULE = "=" * 78
THIN = "-" * 78


# --------------------------------------------------------------------------
# Rendering helpers
# --------------------------------------------------------------------------

def render_citations(citations: list[dict]) -> str:
    lines = []
    for c in citations:
        lines.append(f"  [{c['n']}] {c['source']} :: {c['section']}   chunk={c['chunk_id']}   bm25={c['score']}")
    return "\n".join(lines)


def render_layers(result: dict) -> str:
    lines = []
    for layer in result["evaluation"]["layers"]:
        n, name = layer["layer"], layer["name"]
        if name == "error_typing":
            value = layer["error_type"]
        elif name == "confidence_delta":
            value = f"{layer['before']:.2f} -> {layer['after']:.2f} ({layer['delta']:+.2f})"
        else:
            value = f"{layer['score']:.2f}"
        lines.append(f"  L{n} {name:<20} {value:<26} {layer['detail']}")
    return "\n".join(lines)


def render_progress(progress: dict) -> str:
    lines = []
    for c in progress["concepts"]:
        bar = "#" * round(c["confidence"] * 20)
        mark = " <- current" if c["current"] else ""
        lines.append(
            f"  {c['title']:<24} {c['confidence']:>5.0%}  {bar:<20} attempts={c['attempts']}{mark}"
        )
    return "\n".join(lines)


def _section(title: str) -> None:
    print(f"\n{THIN}\n{title}\n{THIN}")


# --------------------------------------------------------------------------
# demo
# --------------------------------------------------------------------------

def cmd_demo(args: argparse.Namespace) -> int:
    from ale.research.simulate import correct_answer, wrong_answer

    tmp = None
    if args.db:
        db = Path(args.db)
    else:
        tmp = tempfile.TemporaryDirectory(prefix="ale_demo_")
        db = Path(tmp.name) / "demo.db"
    tutor = Tutor(db)
    user = args.user

    print(RULE)
    print("Adaptive Learning Engine - demo of the full adaptive loop")
    print("Building intelligent systems that adapt to human learning.")
    print(RULE)
    print(f"corpus       : {tutor.store.chunk_count('fixture')} chunks from the bundled fixture corpus (local RAG)")
    print("external APIs: none (no keys, no network)")
    print(f"learner state: SQLite at {db}")

    _section(f"1. Start topic '{args.topic}' for user '{user}'")
    state = tutor.start_topic(user, args.topic, restart=True)
    print(f"  session persisted: topic={state['topic_title']} concept={state['concept_title']} phase={state['phase']}")

    # A scripted learner: a conceptual error, then an arithmetic slip, then correct answers.
    script = ["conceptual_error", "calculation_error"] + ["correct"] * 6
    advanced = False
    shown_lesson: list[str] = []
    for round_no, behavior in enumerate(script, start=1):
        s = tutor.state(user)
        concept_title = s["concept_title"]
        lesson = tutor.get_lesson(user)
        problem = tutor.get_problem(user)
        bank = tutor.curriculum.problem(problem["bank_id"])

        _section(f"Round {round_no} - {concept_title} (difficulty {problem['difficulty']}, lesson level: {lesson['level']})")
        lesson_ids = [c["chunk_id"] for c in lesson["citations"]]
        if lesson_ids != shown_lesson:
            shown_lesson = lesson_ids
            print("LESSON (extractive, grounded in retrieved chunks):")
            print(f"  {lesson['adaptation_note']}")
            print("  Citations:")
            print(render_citations(lesson["citations"]))
            if lesson["key_points"]:
                print(f"  Key point: {lesson['key_points'][0]}")
        else:
            print(f"LESSON unchanged (persisted in the session). Citations: {', '.join(lesson_ids)}")
        print(f"PROBLEM [{problem['bank_id']}]: {problem['prompt']}")

        if behavior == "correct":
            answer, reasoning = correct_answer(bank)
        else:
            answer, reasoning = wrong_answer(bank, behavior), ""
        print(f"ANSWER ({behavior}): {answer}" + (f"   reasoning: {reasoning}" if reasoning else ""))

        result = tutor.submit_answer(user, problem["problem_id"], answer, reasoning)
        print(f"EVALUATION: score={result['score']:.2f} correct={result['correct']} error_type={result['error_type']}")
        print(render_layers(result))
        sig = result["learning_signal"]
        print(f"LEARNING SIGNAL: weak_concept={sig['weak_concept']} retry_recommended={sig['retry_recommended']}")
        nxt = result["next_step"]
        print(f"NEXT STEP: {nxt['action'].upper()}  (rule: {nxt['rule']}) -> {nxt['next_concept_title']}, "
              f"difficulty {nxt['difficulty']}, lesson level {nxt['lesson_level']}")
        print(f"  {nxt['reason']}")
        if nxt["action"] == "advance":
            advanced = True
            break

    _section("Progress read back from SQLite")
    progress = tutor.progress(user)
    print(render_progress(progress))

    _section("Persistence check: a separate Python process reads the same state")
    cmd = [sys.executable, "-m", "ale", "progress", "--user", user, "--db", str(db), "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        print("FAILED: could not read progress from a new process", file=sys.stderr)
        return 1
    other = json.loads(proc.stdout)
    if other != progress:
        print("FAILED: state read by the new process differs", file=sys.stderr)
        return 1
    print("  new process returned identical progress (state survived restart)")

    if not advanced:
        print("FAILED: the demo learner never reached an 'advance' decision", file=sys.stderr)
        return 1
    print(f"\n{RULE}\nDemo complete: lesson with citations -> problem -> 5-layer evaluation -> progression -> memory.\n{RULE}")
    if tmp is not None:
        tmp.cleanup()
    return 0


# --------------------------------------------------------------------------
# other commands
# --------------------------------------------------------------------------

def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    if args.db:
        os.environ["ALE_DB"] = args.db
    uvicorn.run("ale.interfaces.api:create_app", factory=True, host=args.host, port=args.port)
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    try:
        import streamlit  # noqa: F401
    except ImportError:
        print("The UI needs Streamlit: pip install 'adaptive-learning-engine[ui]'", file=sys.stderr)
        return 1
    if args.db:
        os.environ["ALE_DB"] = args.db
    script = Path(__file__).with_name("ui.py")
    cmd = [
        sys.executable, "-m", "streamlit", "run", str(script),
        "--server.port", str(args.port), "--server.headless", "true",
        "--browser.gatherUsageStats", "false", "--client.toolbarMode", "minimal",
        "--theme.base", "dark", "--theme.backgroundColor", "#0b0d10",
        "--theme.secondaryBackgroundColor", "#12161b", "--theme.primaryColor", "#6ea8fe",
        "--theme.textColor", "#d7dce2", "--theme.font", "monospace",
    ]
    os.execv(sys.executable, cmd)  # replace this process so Ctrl-C / kill reach Streamlit directly
    return 0  # pragma: no cover


def cmd_ingest(args: argparse.Namespace) -> int:
    tutor = Tutor(args.db or default_db_path())
    for path in args.paths:
        for name, n in ingest_path(tutor.store, Path(path), corpus="user").items():
            print(f"ingested {name}: {n} chunks")
    print(f"total chunks indexed: {tutor.store.chunk_count()}")
    return 0


def cmd_progress(args: argparse.Namespace) -> int:
    tutor = Tutor(args.db or default_db_path())
    progress = tutor.progress(args.user)
    if args.json:
        print(json.dumps(progress, sort_keys=True))
    else:
        print(render_progress(progress))
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    from ale.research.simulate import format_report, run_all

    print(format_report(run_all(args.topic)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ale", description="Adaptive Learning Engine: a local adaptive tutor.")
    p.add_argument("--version", action="version", version=f"ale {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("demo", help="run the full loop on the fixture corpus and exit 0")
    d.add_argument("--topic", default="linear algebra")
    d.add_argument("--user", default="demo")
    d.add_argument("--db", help="persist to this SQLite file (default: a temporary one)")
    d.set_defaults(func=cmd_demo)

    s = sub.add_parser("serve", help="start the HTTP API")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--db")
    s.set_defaults(func=cmd_serve)

    u = sub.add_parser("ui", help="start the Streamlit demo UI")
    u.add_argument("--port", type=int, default=8501)
    u.add_argument("--db")
    u.set_defaults(func=cmd_ui)

    i = sub.add_parser("ingest", help="add your own PDFs / Markdown / text to the local corpus")
    i.add_argument("paths", nargs="+")
    i.add_argument("--db")
    i.set_defaults(func=cmd_ingest)

    g = sub.add_parser("progress", help="print confidence per concept for a user")
    g.add_argument("--user", required=True)
    g.add_argument("--db")
    g.add_argument("--json", action="store_true")
    g.set_defaults(func=cmd_progress)

    m = sub.add_parser("simulate", help="run simulated learners through the loop (research)")
    m.add_argument("--topic", default="linear algebra")
    m.set_defaults(func=cmd_simulate)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except TutorError as exc:
        print(f"error: {exc.message} [{exc.code}]", file=sys.stderr)
        return 1
