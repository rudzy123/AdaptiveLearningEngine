"""SQLite persistence: corpus chunks, sessions, per-concept memory, issued problems, attempts.

One connection per operation (WAL mode), so the API, UI and CLI can share a file and any new
process sees exactly what the last one wrote. There is no in-memory-only state anywhere.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id     TEXT PRIMARY KEY,
    doc_id       TEXT NOT NULL,
    source       TEXT NOT NULL,
    source_title TEXT NOT NULL,
    section      TEXT NOT NULL,
    text         TEXT NOT NULL,
    corpus       TEXT NOT NULL,
    license      TEXT NOT NULL DEFAULT '',
    position     INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);

CREATE TABLE IF NOT EXISTS sessions (
    user_id          TEXT PRIMARY KEY,
    topic            TEXT NOT NULL,
    concept          TEXT NOT NULL,
    difficulty       INTEGER NOT NULL,
    lesson_level     TEXT NOT NULL,
    status           TEXT NOT NULL,
    lesson_json      TEXT,
    problem_id       TEXT,
    last_result_json TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS concept_memory (
    user_id              TEXT NOT NULL,
    concept              TEXT NOT NULL,
    confidence           REAL NOT NULL,
    attempts             INTEGER NOT NULL DEFAULT 0,
    correct              INTEGER NOT NULL DEFAULT 0,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_error_type      TEXT NOT NULL DEFAULT 'none',
    last_score           REAL NOT NULL DEFAULT 0,
    updated_at           TEXT NOT NULL,
    PRIMARY KEY (user_id, concept)
);

CREATE TABLE IF NOT EXISTS problems_issued (
    problem_id  TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    concept     TEXT NOT NULL,
    bank_id     TEXT NOT NULL,
    difficulty  INTEGER NOT NULL,
    status      TEXT NOT NULL,
    issued_at   TEXT NOT NULL,
    answered_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_issued_user ON problems_issued(user_id, concept);

CREATE TABLE IF NOT EXISTS attempts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           TEXT NOT NULL,
    concept           TEXT NOT NULL,
    problem_id        TEXT NOT NULL,
    bank_id           TEXT NOT NULL,
    answer            TEXT NOT NULL,
    reasoning         TEXT NOT NULL,
    score             REAL NOT NULL,
    passed            INTEGER NOT NULL,
    error_type        TEXT NOT NULL,
    confidence_before REAL NOT NULL,
    confidence_after  REAL NOT NULL,
    action            TEXT NOT NULL,
    evaluation_json   TEXT NOT NULL,
    created_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts_user ON attempts(user_id, id);

CREATE TABLE IF NOT EXISTS lesson_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL,
    concept    TEXT NOT NULL,
    level      TEXT NOT NULL,
    chunk_ids  TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


@dataclass
class Session:
    user_id: str
    topic: str
    concept: str
    difficulty: int
    lesson_level: str
    status: str
    lesson: dict | None
    problem_id: str | None
    last_result: dict | None
    created_at: str
    updated_at: str


@dataclass
class ConceptMemory:
    user_id: str
    concept: str
    confidence: float
    attempts: int = 0
    correct: int = 0
    consecutive_failures: int = 0
    last_error_type: str = "none"
    last_score: float = 0.0


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if str(path) == ":memory:":
            raise ValueError("Learner state must be persistent; pass a file path, not ':memory:'.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.tx() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    # meta ---------------------------------------------------------------
    def get_meta(self, key: str) -> str | None:
        with self.tx() as c:
            row = c.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str, conn: sqlite3.Connection | None = None) -> None:
        sql = "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value"
        if conn is not None:
            conn.execute(sql, (key, value))
            return
        with self.tx() as c:
            c.execute(sql, (key, value))

    # chunks -------------------------------------------------------------
    def replace_document(self, doc_id: str, chunks: list[dict[str, Any]]) -> None:
        with self.tx() as c:
            c.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
            c.executemany(
                "INSERT INTO chunks(chunk_id, doc_id, source, source_title, section, text, corpus, license, position) "
                "VALUES(:chunk_id, :doc_id, :source, :source_title, :section, :text, :corpus, :license, :position)",
                chunks,
            )
            version = int(self._meta(c, "chunks_version") or 0) + 1
            self.set_meta("chunks_version", str(version), c)

    @staticmethod
    def _meta(conn: sqlite3.Connection, key: str) -> str | None:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def chunks_version(self) -> int:
        return int(self.get_meta("chunks_version") or 0)

    def all_chunks(self) -> list[dict[str, Any]]:
        with self.tx() as c:
            rows = c.execute("SELECT * FROM chunks ORDER BY doc_id, position").fetchall()
        return [dict(r) for r in rows]

    def chunk_count(self, corpus: str | None = None) -> int:
        with self.tx() as c:
            if corpus:
                row = c.execute("SELECT COUNT(*) AS n FROM chunks WHERE corpus=?", (corpus,)).fetchone()
            else:
                row = c.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()
        return int(row["n"])

    # sessions -----------------------------------------------------------
    def get_session(self, user_id: str) -> Session | None:
        with self.tx() as c:
            r = c.execute("SELECT * FROM sessions WHERE user_id=?", (user_id,)).fetchone()
        if not r:
            return None
        return Session(
            user_id=r["user_id"],
            topic=r["topic"],
            concept=r["concept"],
            difficulty=r["difficulty"],
            lesson_level=r["lesson_level"],
            status=r["status"],
            lesson=json.loads(r["lesson_json"]) if r["lesson_json"] else None,
            problem_id=r["problem_id"],
            last_result=json.loads(r["last_result_json"]) if r["last_result_json"] else None,
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    def save_session(self, s: Session, conn: sqlite3.Connection | None = None) -> None:
        sql = (
            "INSERT INTO sessions(user_id, topic, concept, difficulty, lesson_level, status, lesson_json, "
            "problem_id, last_result_json, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET topic=excluded.topic, concept=excluded.concept, "
            "difficulty=excluded.difficulty, lesson_level=excluded.lesson_level, status=excluded.status, "
            "lesson_json=excluded.lesson_json, problem_id=excluded.problem_id, "
            "last_result_json=excluded.last_result_json, updated_at=excluded.updated_at"
        )
        args = (
            s.user_id, s.topic, s.concept, s.difficulty, s.lesson_level, s.status,
            json.dumps(s.lesson) if s.lesson is not None else None,
            s.problem_id,
            json.dumps(s.last_result) if s.last_result is not None else None,
            s.created_at, now(),
        )
        if conn is not None:
            conn.execute(sql, args)
            return
        with self.tx() as c:
            c.execute(sql, args)

    # memory -------------------------------------------------------------
    def get_memory(self, user_id: str, concept: str, initial: float) -> ConceptMemory:
        with self.tx() as c:
            r = c.execute(
                "SELECT * FROM concept_memory WHERE user_id=? AND concept=?", (user_id, concept)
            ).fetchone()
        if not r:
            return ConceptMemory(user_id, concept, initial)
        return ConceptMemory(
            user_id, concept, r["confidence"], r["attempts"], r["correct"],
            r["consecutive_failures"], r["last_error_type"], r["last_score"],
        )

    def all_memory(self, user_id: str) -> dict[str, ConceptMemory]:
        with self.tx() as c:
            rows = c.execute("SELECT * FROM concept_memory WHERE user_id=?", (user_id,)).fetchall()
        return {
            r["concept"]: ConceptMemory(
                user_id, r["concept"], r["confidence"], r["attempts"], r["correct"],
                r["consecutive_failures"], r["last_error_type"], r["last_score"],
            )
            for r in rows
        }

    def save_memory(self, m: ConceptMemory, conn: sqlite3.Connection) -> None:
        conn.execute(
            "INSERT INTO concept_memory(user_id, concept, confidence, attempts, correct, consecutive_failures, "
            "last_error_type, last_score, updated_at) VALUES(?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(user_id, concept) DO UPDATE SET confidence=excluded.confidence, "
            "attempts=excluded.attempts, correct=excluded.correct, "
            "consecutive_failures=excluded.consecutive_failures, last_error_type=excluded.last_error_type, "
            "last_score=excluded.last_score, updated_at=excluded.updated_at",
            (m.user_id, m.concept, m.confidence, m.attempts, m.correct, m.consecutive_failures,
             m.last_error_type, m.last_score, now()),
        )

    # problems / attempts / lessons --------------------------------------
    def issue_problem(self, user_id: str, concept: str, bank_id: str, difficulty: int) -> str:
        problem_id = new_id("p")
        with self.tx() as c:
            c.execute(
                "INSERT INTO problems_issued(problem_id, user_id, concept, bank_id, difficulty, status, issued_at) "
                "VALUES(?,?,?,?,?,'open',?)",
                (problem_id, user_id, concept, bank_id, difficulty, now()),
            )
        return problem_id

    def get_issued(self, problem_id: str) -> sqlite3.Row | None:
        with self.tx() as c:
            return c.execute("SELECT * FROM problems_issued WHERE problem_id=?", (problem_id,)).fetchone()

    def issue_counts(self, user_id: str, concept: str) -> dict[str, int]:
        with self.tx() as c:
            rows = c.execute(
                "SELECT bank_id, COUNT(*) AS n FROM problems_issued WHERE user_id=? AND concept=? GROUP BY bank_id",
                (user_id, concept),
            ).fetchall()
        return {r["bank_id"]: r["n"] for r in rows}

    def lesson_chunk_ids(self, user_id: str, concept: str) -> list[str]:
        """Chunk ids used by the most recent lesson for this concept (empty if none)."""
        with self.tx() as c:
            r = c.execute(
                "SELECT chunk_ids FROM lesson_history WHERE user_id=? AND concept=? ORDER BY id DESC LIMIT 1",
                (user_id, concept),
            ).fetchone()
        return json.loads(r["chunk_ids"]) if r else []

    def record_lesson(self, user_id: str, concept: str, level: str, chunk_ids: list[str]) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT INTO lesson_history(user_id, concept, level, chunk_ids, created_at) VALUES(?,?,?,?,?)",
                (user_id, concept, level, json.dumps(chunk_ids), now()),
            )

    def recent_attempts(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        with self.tx() as c:
            rows = c.execute(
                "SELECT concept, bank_id, score, passed, error_type, confidence_before, confidence_after, action, "
                "created_at FROM attempts WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(r) | {"passed": bool(r["passed"])} for r in rows]

    # transactional writers used by Tutor.submit_answer --------------------
    def close_problem(self, conn: sqlite3.Connection, problem_id: str) -> None:
        conn.execute(
            "UPDATE problems_issued SET status='answered', answered_at=? WHERE problem_id=?",
            (now(), problem_id),
        )

    def insert_attempt(self, conn: sqlite3.Connection, **row: Any) -> None:
        conn.execute(
            "INSERT INTO attempts(user_id, concept, problem_id, bank_id, answer, reasoning, score, passed, "
            "error_type, confidence_before, confidence_after, action, evaluation_json, created_at) "
            "VALUES(:user_id, :concept, :problem_id, :bank_id, :answer, :reasoning, :score, :passed, "
            ":error_type, :confidence_before, :confidence_after, :action, :evaluation_json, :created_at)",
            {**row, "created_at": now()},
        )
