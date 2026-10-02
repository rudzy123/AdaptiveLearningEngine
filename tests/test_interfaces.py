"""CLI demo and the Streamlit UI."""

import subprocess
import sys
from pathlib import Path

import pytest

from ale.interfaces import cli

UI = str(Path(__file__).resolve().parents[1] / "ale" / "interfaces" / "ui.py")


def test_demo_script_runs_the_whole_loop_and_exits_zero(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "ale", "demo", "--db", str(tmp_path / "demo.db")],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = proc.stdout
    for needle in (
        "Citations:", "chunk=", "bm25=",                      # lesson citations
        "L1 exact_match", "L2 partial_credit", "L3 reasoning_alignment", "L4 error_typing", "L5 confidence_delta",
        "error_type=conceptual_error", "error_type=calculation_error",
        "RETEACH", "REPEAT", "PRACTICE_HARDER", "ADVANCE",      # progression actions
        "LEARNING SIGNAL", "Progress read back", "state survived restart",
    ):
        assert needle in out, needle


def test_progress_command_reads_state_from_a_new_process(tmp_path):
    db = str(tmp_path / "p.db")
    assert cli.main(["demo", "--db", db, "--user", "zed"]) == 0
    proc = subprocess.run([sys.executable, "-m", "ale", "progress", "--user", "zed", "--db", db],
                          capture_output=True, text=True)
    assert proc.returncode == 0
    assert "Vectors" in proc.stdout and "attempts=4" in proc.stdout and "<- current" in proc.stdout


def test_simulate_command(capsys):
    assert cli.main(["simulate"]) == 0
    assert "mastery" in capsys.readouterr().out


def test_ingest_command(tmp_path, capsys):
    doc = tmp_path / "x.txt"
    doc.write_text("Gradient descent follows the negative gradient to minimise a loss function.")
    assert cli.main(["ingest", str(doc), "--db", str(tmp_path / "i.db")]) == 0
    assert "ingested x.txt: 1 chunks" in capsys.readouterr().out
    assert cli.main(["ingest", str(tmp_path / "missing.pdf"), "--db", str(tmp_path / "i.db")]) == 1


def test_streamlit_ui_walks_a_concept_and_survives_a_rerun(tmp_path, monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("ALE_DB", str(tmp_path / "ui.db"))
    at = AppTest.from_file(UI, default_timeout=30)
    at.query_params["user"] = "ada"
    at.run()
    assert not at.exception
    assert any("Adaptive Learning Engine" in m.value for m in at.markdown)

    at.sidebar.button[0].click().run()  # Start / resume
    assert not at.exception
    next(b for b in at.button if b.label == "Load lesson and problem").click().run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Sources" in text and "BM25 score" in text and "Let u = (1, 2)" in text

    next(t for t in at.text_input if t.label == "Answer").set_value("3, 10")
    next(b for b in at.button if b.label == "Submit answer").click().run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "exact / numeric match" in text and "error typing" in text and "confidence delta" in text
    assert "Reteach" in text

    # a "refresh": brand-new AppTest session, same URL and same database file
    again = AppTest.from_file(UI, default_timeout=30)
    again.query_params["user"] = "ada"
    again.run()
    assert not again.exception
    text = " ".join(m.value for m in again.markdown)
    assert "error typing" in text and "Reteach" in text  # the evaluation is still on screen


def test_streamlit_ui_rejects_a_bad_learner_id_without_crashing(tmp_path, monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("ALE_DB", str(tmp_path / "ui.db"))
    at = AppTest.from_file(UI, default_timeout=30)
    at.query_params["user"] = "bad id!"
    at.run()
    assert not at.exception
    assert any("Learner id may use" in e.value for e in at.sidebar.error)
