# Adaptive Learning Engine — REST API

## Run

```bash
cd adaptive_learning_engine
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs

## Architecture

```
app/main.py           → FastAPI + CORS + error handlers + logging
app/api/routes.py     → Thin HTTP handlers
app/api/schemas.py    → Pydantic request/response models
app/services/
  learning_flow.py    → All orchestration logic
  rag_service.py      → PDF chunk retrieval
  user_state_store.py → Per-user topic/concept/problem (SQLite)
```

## Endpoints

### `POST /start_topic`

```json
{ "user_id": "alice", "topic": "linear algebra", "level": "beginner" }
```

```json
{ "message": "Topic initialized", "current_concept": "vectors", "topic": "math" }
```

### `POST /get_lesson`

```json
{ "user_id": "alice" }
```

```json
{ "concept": "eigenvalues", "lesson": "text explanation…" }
```

### `POST /get_problem`

```json
{ "user_id": "alice" }
```

```json
{ "problem": "Find eigenvalues…", "difficulty": "medium", "concept": "eigenvalues" }
```

### `POST /submit_answer`

```json
{ "user_id": "alice", "answer": "2 and 3" }
```

```json
{
  "is_correct": false,
  "score": 0.6,
  "error_type": "calculation_error",
  "feedback": "…",
  "hint": "…",
  "confidence": 0.45,
  "next_action": "repeat"
}
```

### `POST /next_step`

```json
{ "user_id": "alice" }
```

```json
{ "next_concept": "determinants", "action": "advance", "message": "…" }
```

### `GET /progress/{user_id}`

```json
{
  "topic": "linear algebra",
  "concepts": [
    { "name": "vectors", "confidence": 0.9, "label": "Vectors", "attempts": 3 }
  ]
}
```

### `GET /test/loop/{user_id}`

Runs initialize → lesson → problem → evaluate → next in one call (dev only).

## Errors

All errors return:

```json
{ "error": "message" }
```

## Test script

```bash
python app/tests/test_learning_loop.py
```
