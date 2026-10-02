# Adaptive Learning Engine (ALE) - Public Deployment Guide

This guide is written for professors, engineers, and recruiters who want to run, demo, and evaluate ALE quickly.

## 1) Overview

**Adaptive Learning Engine (ALE)** is a production-grade adaptive tutoring system that teaches complex subjects through:

- persistent learner memory,
- multi-layer answer evaluation,
- progression decisions based on confidence and error type,
- and RAG-grounded lesson context from ingested PDFs.

### Core components

- **FastAPI backend**: `app/main.py`
  - REST API, validation, structured errors, observability logging.
- **Learning engine**: `engine/`
  - Memory (`memory.py`) + progression (`progression.py`) + concept sequencing.
- **RAG system**: `pipeline/` + `app/services/rag_service.py`
  - Retrieves relevant PDF chunks and adds source citations to lessons.
- **Frontend**: `web/` (Next.js + Tailwind)
  - Clean dashboard for topic -> lesson -> problem -> feedback flow.

---

## 2) Local deployment (required)

### Prerequisites

- Python 3.11+ (3.12 recommended)
- Node.js 18+ and npm
- Git

### Step-by-step

1. **Clone repository**

```bash
git clone <YOUR_REPO_URL>
cd adaptive_learning_engine
```

2. **Create and activate virtual environment**

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

3. **Install backend dependencies**

```bash
pip install -r requirements.txt
```

4. **Run backend**

```bash
uvicorn app.main:app --reload --port 8000
```

5. **Run frontend**

```bash
cd web
cp .env.local.example .env.local
npm install
npm run dev
```

6. **Open browser**

- Frontend: [http://localhost:3000](http://localhost:3000)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 3) Data setup

### Where to place PDFs

Place source PDFs under the workspace-level corpus directory:

```text
learning_engine_data/
  math/
  physics/
  cs/
  problems/
```

> The corpus lives outside the Python package so large datasets remain separated from app code.

### Ingestion command

From `adaptive_learning_engine/`:

```bash
python scripts/ingest_pdfs.py
python tag_chunks.py
python build_curriculum.py
```

### Where processed data is stored

- Chunk DB: `../learning_engine_data/processed/learning_chunks.db`
- Optional JSON chunks: `../learning_engine_data/processed/chunks_json/`
- Curriculum JSON: `../learning_engine_data/processed/curriculum/learning_path.json`
- Runtime state/logs: `data/*.db`

---

## 4) API testing without frontend (important)

### A) Start topic

```bash
curl -s -X POST http://localhost:8000/start_topic \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo_user","topic":"linear algebra","level":"beginner"}' | jq
```

Typical response:

```json
{
  "status": "success",
  "data": {
    "message": "Topic initialized",
    "current_concept": "linear_algebra",
    "topic": "math",
    "topic_label": "linear algebra"
  }
}
```

### B) Get lesson

```bash
curl -s http://localhost:8000/lesson/demo_user | jq
```

### C) Get problem

```bash
curl -s http://localhost:8000/problem/demo_user | jq
```

### D) Submit answer

```bash
curl -s -X POST http://localhost:8000/submit_answer \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo_user","answer":"I think eigenvalues are the determinant only."}' | jq
```

### E) Decide next step

```bash
curl -s -X POST http://localhost:8000/next_step/demo_user | jq
```

### F) Progress snapshot

```bash
curl -s http://localhost:8000/progress/demo_user | jq
```

---

## 5) Demo walkthrough (critical)

Sample flow to present ALE in a meeting:

1. **Start topic: Linear Algebra**
   - `POST /start_topic` with `demo_user`.
2. **Get lesson**
   - `GET /lesson/demo_user` (show explanation + citations).
3. **Get problem**
   - `GET /problem/demo_user`.
4. **Submit answer**
   - `POST /submit_answer` and inspect:
     - `is_correct`, `score`, `error_type`, `feedback`, `hint`,
     - `learning_signal`.
5. **Show progression**
   - `POST /next_step/demo_user` (advance/repeat/reteach/review behavior).

---

## 6) Optional public deployment (advanced)

### Backend (FastAPI)

Pick one:

- **Railway**: easy Docker/Python service deployment.
- **Render**: web service with `uvicorn app.main:app`.
- **Docker**: portable deployment anywhere.

Generic backend flow:

1. Push repository to GitHub.
2. Create backend service on Railway/Render.
3. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. Ensure persistent storage for SQLite files (`data/*.db`) if needed.

### Frontend (Next.js, recommended: Vercel)

1. Push repo to GitHub.
2. Import project in Vercel.
3. Set root directory to `web/`.
4. Set env var `NEXT_PUBLIC_API_URL` to deployed backend URL.
5. Deploy.

---

## 7) Environment variables

Create `.env.example` in repo root (already included) and copy to `.env` if needed:

```env
APP_ENV=development
DB_PATH=./data
LOG_LEVEL=info
API_HOST=0.0.0.0
API_PORT=8000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 8) Troubleshooting

### Backend fails to start

- Verify venv is active.
- Reinstall deps: `pip install -r requirements.txt`.
- Confirm import path: run from `adaptive_learning_engine/`.

### Frontend cannot reach API

- Check backend is running on `:8000`.
- Check `web/.env.local` has `NEXT_PUBLIC_API_URL=http://localhost:8000`.
- Check browser console/network for CORS or URL issues.

### PDFs not appearing in lessons

- Verify PDFs exist under `../learning_engine_data/*`.
- Re-run:
  - `python scripts/ingest_pdfs.py`
  - `python tag_chunks.py`
- Confirm chunk DB exists:
  - `../learning_engine_data/processed/learning_chunks.db`

### API returns structured errors

- ALE intentionally returns:
  - `{"status":"error","error":{"message":"...","code":...}}`
- Use the message to correct input (user_id/topic/answer/session state).

---

## 9) System demo script

Run:

```bash
python scripts/demo.py
```

It executes one full loop:

- start topic
- lesson retrieval
- problem generation
- answer evaluation
- progression decision
- progress snapshot

This is the fastest way to validate ALE end-to-end from terminal output.

---

## 10) Final checklist for evaluators

Anyone should now be able to:

- clone repository,
- run backend and frontend locally,
- execute API calls directly,
- run the demo script,
- and understand architecture and adaptive behavior through docs.

