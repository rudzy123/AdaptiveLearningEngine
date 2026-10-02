# Adaptive Learning Web UI

Next.js 14 + React + Tailwind dashboard for the Adaptive Learning Engine.

## Run locally

**Terminal 1 — API** (from `adaptive_learning_engine/`):

```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Web**:

```bash
cd web
cp .env.local.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/start_topic` | Start session, load first lesson |
| GET | `/lesson/{user_id}` | Retrieve lesson for current concept |
| GET | `/problem/{user_id}` | Retrieve current problem |
| POST | `/submit_answer` | Evaluate answer, return feedback |
| POST | `/next_step/{user_id}` | Advance to next problem or concept |
| GET | `/progress/{user_id}` | Retrieve confidence progression |

## Layout

- **Sidebar** — topics, per-concept confidence, weak-area highlights
- **Main** — lesson card, problem card, feedback card (green/red)
