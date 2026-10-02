# Adaptive Learning Engine (ALE) Architecture

## System definition

**Adaptive Learning Engine (ALE)** is a production-grade adaptive tutoring system that uses memory, evaluation, and progression to teach complex subjects.

## High-level diagram

```text
User / Client
   |
   v
FastAPI (app/main.py)
   |
   v
API Layer (app/api/routes.py, schemas.py, envelope.py)
   |
   v
LearningSession Orchestrator (app/services/learning_session.py)
   |-------------------------|---------------------------|
   v                         v                           v
RAG Service             Engine Layer                 Generation Layer
(app/services/          (engine/)                    (generation/)
 rag_service.py)        - memory.py                  - evaluation.py
   |                    - progression.py
   v                    - concepts.py
Pipeline Retrieval      - lesson_generator.py
(pipeline/retrieval.py) - problem_generator.py
   |
   v
learning_engine_data/processed/learning_chunks.db

Data Layer (data/)
  - session_repository.py  -> data/session_state.db
  - api_log_repository.py  -> data/logs.db
  - engine memory store    -> data/user_progress.db
```

## Separation of concerns

- **API layer** (`app/api/`): request parsing, response envelope, route mapping only.
- **Service layer** (`app/services/`): all business logic and orchestration.
- **Engine layer** (`engine/`): progression, memory, concepts, generators.
- **Generation layer** (`generation/`): answer evaluation and feedback quality.
- **Data layer** (`data/`): durable session state and structured observability logs.

## Request lifecycle

1. API route validates payload shape (Pydantic).
2. `LearningSession` validates semantics (user/topic/answer).
3. Session is loaded from `session_state`.
4. Operation runs (lesson/problem/evaluation/progression).
5. Session is saved back to `session_state`.
6. Structured response envelope returned.
7. Observability row written to `logs.db`.

## State model

`session_state` persists:

- `user_id`
- `topic`
- `current_concept`
- `last_problem`
- `last_updated`

and extended fields (`concepts_json`, `concept_index`, `phase`, etc.) for complete recoverability.

## API contract

- `POST /start_topic`
- `GET /lesson/{user_id}`
- `GET /problem/{user_id}`
- `POST /submit_answer`
- `POST /next_step/{user_id}`
- `GET /progress/{user_id}`

Response format:

- Success: `{"status":"success","data":{...}}`
- Error: `{"status":"error","error":{"message":"...","code":400}}`

