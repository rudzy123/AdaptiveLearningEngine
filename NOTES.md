# NOTES

Handoff notes for the rewrite of this repository into a local adaptive tutor. Reviewed against the
code before the rewrite was committed. Not pushed, and no pull request was opened.

## What changed

**Replaced.** The previous layout had several overlapping implementations of the same ideas (`app/`,
`engine/`, `generation/`, `pipeline/`, `rag/`, `api/`, plus root scripts and a `web/` frontend). They are
deleted and replaced by one package:

- `ale/engine/` the core: ingest, BM25 retrieval, extractive lessons, problem selection, the five
  evaluation layers, the progression policy, the SQLite store, and the `Tutor` service.
- `ale/interfaces/` one FastAPI app, one Streamlit UI, one CLI (`python -m ale ...`).
- `ale/research/simulate.py` simulated learners.
- `ale/engine/data/` the curriculum (7 concepts, 28 problems) and the original fixture corpus.

**Deleted.** `app/`, `engine/`, `generation/`, `pipeline/`, `rag/`, `api/`, `scripts/`, `web/` (the unused
frontend), `config.py`, the root scripts (`build_curriculum.py`, `download_materials.py`, `ingest_pdfs.py`,
`learn_cli.py`, `retrieve_for_lesson.py`, `tag_chunks.py`), `requirements.txt`, `pytest.ini`, `.env.example`
(no keys are needed), and the old `docs/`.

**Rewritten.** `README.md`, `.gitignore`, and the `tests/`. New: `pyproject.toml`, `.streamlit/config.toml`,
`docs/demo.md`, three screenshots in `docs/`, and this file.

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
python -m ale demo
python -m ale ui         # http://localhost:8501/?user=ada
python -m ale serve      # http://127.0.0.1:8000/docs
```

Details and what to look for are in `docs/demo.md`.

## Verification performed

- `pytest`: all tests pass (162 at the last run). They cover the API envelope and validation, no stack-trace
  leaks, each evaluation layer, all 28 bank problems (the stored correct answer scores 1.0, the stored wrong
  answers hit their typed error), each progression action, session recovery from a fresh `Tutor` and a fresh
  app, citation shape and grounding, a PDF ingest with a hand-built PDF, the demo script as a subprocess
  (exit 0), and a Streamlit `AppTest` walk including a refresh.
- Mutation checks: several deliberate breakages (for example swapping a progression threshold, dropping a
  layer, removing the persisted lesson) each made at least one test fail.
- `python -m ale demo` exits 0 and prints citations, the five layers, error type, next step, and progress,
  then confirms a separate process reads the same SQLite state.
- The UI was driven in a real browser: lesson, wrong answer (RETEACH), correct answers (ADVANCE), a server
  restart, and a page reload, with state preserved. The screenshots in `docs/` come from that session.
  The third screenshot's two correct answers were submitted through the engine against the same database,
  not by clicking in the UI (see `docs/demo.md`).
- The HTTP API was exercised with `curl` against a real server (health, session, lesson, problem, answer,
  validation error).

## Interpretation decisions

- **"5-layer evaluation"**: the five layers are exact/numeric match, partial credit, reasoning alignment,
  error typing, confidence delta. The site does not define them, so this is my reading.
- **Failed answers never advance.** A literal reading of the confidence bands could advance a learner whose
  last answer was wrong but whose EMA is high. Rule 4 in `progression.py` sends any failed answer to
  `repeat`, so the confidence bands only apply after a passing answer. Tests pin this.
- **Reteach is triggered by error type, not only by low confidence**, and by three consecutive failures.
- **Envelope**: success is `{"status": "success", "data": ...}`; errors are
  `{"status": "error", "error": {"message", "code"}}`.
- **Learner id is the identity.** There is no authentication. The id is a validated string, and the UI keeps
  it in the URL. Anyone who knows an id can read or advance that learner.
- **`:memory:` databases are refused**, because they would defeat the persistence claim.

## Real limits

- **Tiny corpus.** The fixture corpus is hand-written, about 28 short sections across 7 concepts. Lessons
  are only as good as that text.
- **Lessons are extractive.** Passages are selected and ordered, key points are picked by overlap with the
  concept; nothing is generated. They read like study notes, not a tutor's explanation.
- **Lexical retrieval only.** BM25 with a relevance floor. No embeddings, so paraphrases without shared
  vocabulary are missed.
- **Template problem bank.** 28 fixed problems (4 per concept). With enough attempts the learner will see
  repeats. Answers are checked by numeric/phrase/Big-O matching, not by understanding.
- **Error typing is heuristic.** It uses known wrong-answer signatures per problem plus partial-correctness
  rules. Anything unrecognised falls through to generic rules (for example, an off-by-more-than-a-slip
  numeric answer is labeled `conceptual_error`), so novel mistakes can be mislabeled.
- **Confidence is an EMA, not a calibrated probability.** The thresholds (0.5, 0.8, learning rates 0.6/0.4)
  are chosen by hand, not fit to data.
- **Simulated learners are not evidence.** `python -m ale simulate` checks that the policy behaves sensibly
  against scripted personas. There are no real-learner results, no outcome metrics, and no deployment
  numbers anywhere in this repo.
- **Optional documents only add retrieval text.** `python -m ale ingest` adds chunks for the existing
  concepts. It does not create new concepts or problems, and no downloader or large corpus is shipped.
- **PDF extraction** depends on `pypdf` and on PDFs that contain a text layer. Scanned PDFs yield nothing.
- **Environment.** Tested on Python 3.14 on Linux only. `pyproject.toml` declares 3.10+, which is untested.
  Starting the Streamlit server or the API needs permission to bind a local port, which some sandboxes
  block.
- **Single-process design.** SQLite with a connection per operation is fine for a demo; there is no
  concurrency tuning, migration tooling, or backup story.

## Checked before commit

- On the files git already tracked, `git diff --stat` is 115 files, +660 / −13699: the old packages
  deleted and `README.md`, `.gitignore` and the existing tests rewritten. The new package (`ale/`,
  `pyproject.toml`, `docs/`, `NOTES.md`, the new tests) was untracked, so it appears only after staging.
- Runtime databases (`data/`), logs, `.venv`, caches and PDFs are ignored by `.gitignore`.
- The screenshots in `docs/` are about 0.7 MB in total.
