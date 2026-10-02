# Demo guide

Everything below runs offline. No API keys, no network.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 1. Tests

```bash
pytest
```

Expect all tests to pass. They cover the API envelope and validation, each evaluation layer, each
progression action, session recovery, citation shape, the demo script, a full HTTP loop on the fixture
corpus, and a Streamlit walk-through with a page refresh.

## 2. One-command terminal demo

```bash
python -m ale demo
```

It uses a temporary SQLite file and exits 0. You should see, in order:

1. `corpus: 28 chunks from the bundled fixture corpus` and `external APIs: none`.
2. **Round 1, Vectors.** A lesson with numbered citations such as
   `[1] linear_algebra_notes.md :: Vectors - Intuition  chunk=linear_algebra_notes#000  bm25=...`.
   The scripted learner answers `3, 10` to `u + v` (they multiplied instead of adding).
   The five evaluation layers print, error type is `conceptual_error`, confidence drops `0.20 -> 0.08`,
   and the next step is `RETEACH` at an easier level.
3. **Round 2.** A different, shorter lesson (`lesson level: easy`). A calculation slip gives a partial
   score (`0.38`), error type `calculation_error`, and `REPEAT` with no reteach.
4. **Rounds 3 and 4.** Correct answers raise confidence (`0.26 -> 0.70`), then `PRACTICE_HARDER`, then
   `0.70 -> 0.82` and `ADVANCE` to Dot Product.
5. **Progress read back from SQLite**, followed by a check that a separate Python process reads identical
   state.

The exact numbers are deterministic for the bundled corpus and curriculum. Bar widths and temporary paths
differ per run.

To keep the database and inspect it afterwards:

```bash
python -m ale demo --db /tmp/ale_demo.db
python -m ale progress --user demo --db /tmp/ale_demo.db
```

## 3. Streamlit UI

```bash
python -m ale ui
```

Open <http://localhost:8501/?user=ada>. The learner id lives in the URL, so a refresh keeps the learner.

1. Click **Start / resume**, then **Continue**. The lesson appears with its sources (chunk id and BM25
   score) and a practice problem.
2. Enter `3, 10` as the answer and submit. The five-layer table appears with `conceptual error`, and the
   next step is a red **RETEACH** badge.
3. Click **Continue** for the easier lesson, answer correctly (for example `4, 7`), and watch confidence
   rise in the sidebar.
4. Keep answering correctly until the badge turns green (**ADVANCE**).
5. Refresh the page, or stop the server and start it again with the same `ALE_DB`. Confidence per concept,
   the current concept and the last evaluation are still there.

![Lesson with sources](screenshot-lesson.png)

![Evaluation and RETEACH](screenshot-evaluation.png)

![After server restart and refresh](screenshot-after-restart.png)

These three images were captured from the running UI for learner `ada`. The first two show the first
attempt (the wrong answer `3, 10`). The third was taken after two correct answers were submitted through
the engine API against the same database and the server was restarted, so it shows a restored session
(`vec-2` answered `5`, confidence `0.63 -> 0.85`, ADVANCE to Dot Product).

## 4. HTTP API

```bash
python -m ale serve            # http://127.0.0.1:8000, interactive docs at /docs
```

In a second terminal:

```bash
curl -s localhost:8000/health
curl -s -X POST localhost:8000/api/sessions -H 'content-type: application/json' \
     -d '{"user_id": "ada", "topic": "linear algebra"}'
curl -s localhost:8000/api/users/ada/lesson
curl -s localhost:8000/api/users/ada/problem
curl -s -X POST localhost:8000/api/users/ada/answers -H 'content-type: application/json' \
     -d '{"problem_id": "<problem_id from the previous call>", "answer": "3, 10"}'
curl -s localhost:8000/api/users/ada/progress
```

Every response is `{"status": "success", "data": ...}` or
`{"status": "error", "error": {"message": ..., "code": ...}}`. For example, a missing field returns
`code: validation_error` with HTTP 422 and no stack trace.

## 5. Simulated learners

```bash
python -m ale simulate
```

Four scripted personas run through the real loop. Expected: `mastery`, `careless` and `confused` complete
the Linear Algebra topic; `struggling` (never answers correctly) does not, and keeps cycling through
`repeat` and `reteach`.
