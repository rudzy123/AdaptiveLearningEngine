# Adaptive Learning Engine (ALE)

**Adaptive Learning Engine (ALE)** is a local, production-oriented adaptive tutoring system that uses memory, evaluation, and progression to teach complex subjects. It ingests open PDFs, retrieves grounded context, generates lessons/problems, and adapts sequencing over time. **No external API keys.**

## Quick start

```bash
cd adaptive_learning_engine
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Knowledge base (one-time)
python scripts/download_materials.py
python scripts/ingest_pdfs.py
python build_curriculum.py
python tag_chunks.py

# API server (recommended)
uvicorn app.main:app --reload --port 8000
# Docs: http://localhost:8000/docs

# Tests
pytest tests/ -q

# Demo (full loop)
python scripts/demo.py

# CLI (interactive terminal)
python app/cli_main.py

# Streamlit panel
streamlit run app/learning_panel.py

# Next.js UI (optional)
cd web && npm install && npm run dev
```

## System architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Clients: Next.js (web/) · Streamlit · CLI · curl               │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP JSON
┌────────────────────────────▼────────────────────────────────────┐
│  API LAYER          app/api/routes.py  app/api/schemas.py       │
│                     app/api/envelope.py  (success | error)      │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  SERVICE LAYER      app/services/learning_session.py  (orch.)   │
│                     app/services/rag_service.py               │
│                     app/services/validation.py                  │
│                     app/services/observability.py               │
└──────┬─────────────────────┬──────────────────────┬───────────┘
       │                     │                      │
┌──────▼──────┐    ┌─────────▼─────────┐   ┌───────▼──────────────┐
│ DATA LAYER  │    │ ENGINE            │   │ GENERATION         │
│ data/       │    │ engine/           │   │ generation/        │
│ session_    │    │ memory            │   │ evaluation.py      │
│ repository  │    │ progression       │   │ (5-layer eval)     │
│ api_logs    │    │ concepts          │   │                    │
│             │    │ lesson_generator  │   │                    │
│ data/*.db   │    │ problem_generator │   │                    │
└─────────────┘    └─────────┬─────────┘   └────────────────────┘
                             │
                    ┌────────▼────────┐
                    │ pipeline/       │
                    │ retrieval · PDF   │
                    │ learning_chunks.db│
                    └───────────────────┘
```

### Learning loop (data flow)

1. **POST /start_topic** — curriculum loaded → `session_state` row created in SQLite.
2. **GET /lesson/{user_id}** — RAG retrieves chunks → lesson text + `citations[]`.
3. **GET /problem/{user_id}** — problem generator → `last_problem` persisted.
4. **POST /submit_answer** — `generation/evaluation` → `engine/memory` updated → progression signal.
5. **POST /next_step/{user_id}** — advance concept or repeat/reteach/review.
6. **GET /progress/{user_id}** — confidence per concept from `user_progress.db`.

### Evaluation logic (`generation/evaluation.py`)

| Layer | Purpose |
|-------|---------|
| 1 | Exact / numeric match |
| 2 | Partial credit |
| 3 | Reasoning alignment |
| 4 | Error typing (`conceptual_error`, `calculation_error`, …) |
| 5 | Confidence delta → memory |

API adds **`learning_signal`**: `{ weak_concept, retry_recommended }`.

### Progression logic (`engine/progression.py`)

| Signal | Action |
|--------|--------|
| confidence ≥ 0.8 | **advance** |
| 0.5 – 0.8 | **practice_harder** (harder problems) |
| < 0.5 | **repeat** / reteach |
| conceptual / misinterpretation | **reteach** at beginner |
| calculation_error | more practice, not full reteach |
| 3+ consecutive failures | reteach |

`decide_from_evaluation()` bridges evaluation → progression on every answer.

## API design

All successful responses:

```json
{ "status": "success", "data": { ... } }
```

Errors (never raw stack traces):

```json
{ "status": "error", "error": { "message": "description", "code": 400 } }
```

| Method | Path | Action |
|--------|------|--------|
| POST | `/start_topic` | Initialize topic |
| GET | `/lesson/{user_id}` | Lesson + RAG chunks + citations |
| GET | `/problem/{user_id}` | One practice problem |
| POST | `/submit_answer` | Evaluate + update memory |
| POST | `/next_step/{user_id}` | Progression |
| GET | `/progress/{user_id}` | Confidence by concept |

Legacy POST aliases: `/get_lesson`, `/get_problem`, `/next_step` (body: `{ "user_id" }`).

## Session state (critical)

**No in-memory session store.** Every request:

1. `SessionRepository.load(user_id)`
2. Business logic in `LearningSession`
3. `SessionRepository.save(user_id)`

Table: `data/session_state.db` → `session_state`  
Columns: `user_id`, `topic`, `current_concept`, `last_problem`, `last_updated` (+ extended fields for recoverability).

## Observability

- **File logs**: `logs/` via `pipeline/logging_setup.py`
- **SQLite**: `data/logs.db` → `api_logs` (endpoint, user_id, concept, latency_ms, score, error_type)

## Package layout

```
adaptive_learning_engine/
├── app/
│   ├── main.py                 # FastAPI entry (uvicorn app.main:app)
│   ├── cli_main.py             # Terminal CLI
│   ├── api/                    # routes, schemas, envelope
│   └── services/               # learning_session, rag, validation
├── data/                       # session_repository, api_log_repository
├── engine/                     # memory, progression, generators
├── generation/                 # deep evaluation
├── pipeline/                   # ingest, retrieval, curriculum
├── tests/                      # pytest: test_api, test_evaluation, test_progression
├── data/*.db                   # runtime databases
└── web/                        # Next.js dashboard
```

## Additional docs

- Architecture: `docs/architecture.md`
- Design retrospectives: `docs/lessons_learned.md`
- Public deployment guide: `docs/deployment_guide.md`

Corpus PDFs: `../learning_engine_data/` (outside package).

## Testing

```bash
pytest tests/ -q
```

- `test_api.py` — full HTTP loop + envelope + validation
- `test_evaluation.py` — scoring / error types
- `test_progression.py` — advance vs reteach rules

## RAG output shape

```json
{
  "chunks": [{ "text": "...", "source": "linear_algebra.pdf", "score": 0.87 }],
  "citations": ["Source: linear_algebra.pdf (Section Eigenvalues)"]
}
```

Retrieval is **LRU-cached** per `(topic, concept, weak_concepts)` in `RagService`.

## License

Course PDFs © respective institutions (MIT OCW, Stanford). Pipeline respects public open licenses.
