"""Persistent user learning state and answer logging."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from config import ENGINE_DATA_DIR, RETEACH_FAILURE_THRESHOLD, USER_PROGRESS_DB_PATH

logger = logging.getLogger(__name__)

LearnerLevel = Literal["beginner", "intermediate", "advanced"]

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    current_level TEXT NOT NULL DEFAULT 'beginner',
    current_concept TEXT,
    last_active TEXT,
    PRIMARY KEY (user_id, topic)
);

CREATE TABLE IF NOT EXISTS user_progress (
    user_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    concept TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    confidence_score REAL NOT NULL DEFAULT 0.0,
    consecutive_wrong INTEGER NOT NULL DEFAULT 0,
    last_updated TEXT NOT NULL,
    PRIMARY KEY (user_id, topic, concept)
);

CREATE INDEX IF NOT EXISTS idx_progress_user_topic
    ON user_progress(user_id, topic);

CREATE TABLE IF NOT EXISTS answer_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    concept TEXT NOT NULL,
    correct INTEGER NOT NULL,
    difficulty TEXT NOT NULL,
    user_answer TEXT,
    expected_answer TEXT,
    mistake_type TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_answer_log_user
    ON answer_log(user_id, created_at);
"""


@dataclass
class UserProgress:
    """Per-user, per-concept learning record."""

    user_id: str
    topic: str
    concept: str
    attempts: int
    correct_count: int
    confidence_score: float
    last_updated: str
    consecutive_wrong: int = 0

    @property
    def correctness_rate(self) -> float:
        if self.attempts == 0:
            return 0.0
        return self.correct_count / self.attempts


@dataclass
class UserTopicProfile:
    """High-level learner profile for one topic."""

    user_id: str
    topic: str
    current_level: LearnerLevel
    current_concept: str
    last_active: str


class MemoryStore:
    """
    SQLite-backed store for learner progress and answer history.

    Confidence uses Laplace-smoothed accuracy blended with recency so
    early attempts do not over-penalize or over-reward.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or USER_PROGRESS_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            self._migrate(conn)
            conn.commit()

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Apply lightweight schema upgrades for analytics."""
        try:
            conn.execute(
                "ALTER TABLE answer_log ADD COLUMN confidence_after REAL"
            )
        except sqlite3.OperationalError:
            pass  # column already exists

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def ensure_user_topic(
        self,
        user_id: str,
        topic: str,
        level: LearnerLevel = "beginner",
        current_concept: str = "",
    ) -> UserTopicProfile:
        """Create or update a user profile for a topic."""
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_profiles (user_id, topic, current_level,
                                           current_concept, last_active)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, topic) DO UPDATE SET
                    last_active = excluded.last_active,
                    current_level = COALESCE(
                        user_profiles.current_level, excluded.current_level
                    )
                """,
                (user_id, topic, level, current_concept, now),
            )
            conn.commit()
        return self.get_profile(user_id, topic) or UserTopicProfile(
            user_id=user_id,
            topic=topic,
            current_level=level,
            current_concept=current_concept,
            last_active=now,
        )

    def get_profile(self, user_id: str, topic: str) -> UserTopicProfile | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id, topic, current_level, current_concept, last_active
                FROM user_profiles WHERE user_id = ? AND topic = ?
                """,
                (user_id, topic),
            ).fetchone()
        if not row:
            return None
        return UserTopicProfile(
            user_id=row["user_id"],
            topic=row["topic"],
            current_level=row["current_level"],
            current_concept=row["current_concept"] or "",
            last_active=row["last_active"] or "",
        )

    def set_profile(
        self,
        user_id: str,
        topic: str,
        *,
        current_level: LearnerLevel | None = None,
        current_concept: str | None = None,
    ) -> None:
        self.ensure_user_topic(user_id, topic)
        updates: list[str] = ["last_active = ?"]
        values: list[str] = [self._now()]
        if current_level is not None:
            updates.append("current_level = ?")
            values.append(current_level)
        if current_concept is not None:
            updates.append("current_concept = ?")
            values.append(current_concept)
        values.extend([user_id, topic])
        with self._connect() as conn:
            conn.execute(
                f"UPDATE user_profiles SET {', '.join(updates)} "
                f"WHERE user_id = ? AND topic = ?",
                values,
            )
            conn.commit()

    def get_user_progress(
        self, user_id: str, topic: str | None = None
    ) -> list[UserProgress]:
        """Return all concept progress rows for a user (optionally filtered by topic)."""
        query = "SELECT * FROM user_progress WHERE user_id = ?"
        params: list[str] = [user_id]
        if topic:
            query += " AND topic = ?"
            params.append(topic)
        query += " ORDER BY topic, concept"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            UserProgress(
                user_id=r["user_id"],
                topic=r["topic"],
                concept=r["concept"],
                attempts=r["attempts"],
                correct_count=r["correct_count"],
                confidence_score=r["confidence_score"],
                last_updated=r["last_updated"],
                consecutive_wrong=r["consecutive_wrong"],
            )
            for r in rows
        ]

    def get_concept_progress(
        self, user_id: str, topic: str, concept: str
    ) -> UserProgress | None:
        rows = [
            p
            for p in self.get_user_progress(user_id, topic)
            if p.concept == concept
        ]
        return rows[0] if rows else None

    @staticmethod
    def compute_confidence(attempts: int, correct_count: int) -> float:
        """
        Compute confidence in [0, 1] using smoothed accuracy.

        Uses (correct + 1) / (attempts + 2) Laplace smoothing so new
        learners start near 0.5 rather than 0 or 1.
        """
        if attempts <= 0:
            return 0.0
        smoothed = (correct_count + 1) / (attempts + 2)
        return round(min(1.0, max(0.0, smoothed)), 4)

    def update_progress(
        self,
        user_id: str,
        topic: str,
        concept: str,
        correct: bool,
        *,
        difficulty: str = "beginner",
        user_answer: str = "",
        expected_answer: str = "",
        mistake_type: str | None = None,
        score: float | None = None,
        confidence_delta: float = 0.0,
    ) -> UserProgress:
        """
        Record an attempt and refresh confidence for one concept.

        Also logs the answer to answer_log for audit and analytics.
        """
        self.ensure_user_topic(user_id, topic)
        existing = self.get_concept_progress(user_id, topic, concept)
        now = self._now()

        if existing:
            attempts = existing.attempts + 1
            if score is not None and score >= 0.7:
                correct_count = existing.correct_count + 1
            elif score is not None and score >= 0.4:
                correct_count = existing.correct_count  # partial — no full credit
            else:
                correct_count = existing.correct_count + (1 if correct else 0)
            consecutive_wrong = (
                0 if correct or (score is not None and score >= 0.7)
                else existing.consecutive_wrong + 1
            )
        else:
            attempts = 1
            correct_count = 1 if (correct or (score is not None and score >= 0.7)) else 0
            consecutive_wrong = 0 if correct else 1

        confidence = self.compute_confidence(attempts, correct_count)
        if confidence_delta:
            confidence = round(
                min(1.0, max(0.0, confidence + confidence_delta)), 4
            )

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_progress
                (user_id, topic, concept, attempts, correct_count,
                 confidence_score, consecutive_wrong, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, topic, concept) DO UPDATE SET
                    attempts = excluded.attempts,
                    correct_count = excluded.correct_count,
                    confidence_score = excluded.confidence_score,
                    consecutive_wrong = excluded.consecutive_wrong,
                    last_updated = excluded.last_updated
                """,
                (
                    user_id,
                    topic,
                    concept,
                    attempts,
                    correct_count,
                    confidence,
                    consecutive_wrong,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO answer_log
                (user_id, topic, concept, correct, difficulty,
                 user_answer, expected_answer, mistake_type, created_at,
                 confidence_after)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    topic,
                    concept,
                    1 if correct else 0,
                    difficulty,
                    user_answer,
                    expected_answer,
                    mistake_type,
                    now,
                    confidence,
                ),
            )
            conn.commit()

        logger.info(
            "Progress updated: user=%s concept=%s correct=%s confidence=%.2f",
            user_id,
            concept,
            correct,
            confidence,
        )

        return UserProgress(
            user_id=user_id,
            topic=topic,
            concept=concept,
            attempts=attempts,
            correct_count=correct_count,
            confidence_score=confidence,
            last_updated=now,
            consecutive_wrong=consecutive_wrong,
        )

    def get_weak_areas(
        self, user_id: str, topic: str | None = None, threshold: float = 0.5
    ) -> list[UserProgress]:
        """Concepts with confidence below threshold, weakest first."""
        progress = self.get_user_progress(user_id, topic)
        weak = [p for p in progress if p.confidence_score < threshold and p.attempts > 0]
        weak.sort(key=lambda p: (p.confidence_score, -p.attempts))
        return weak

    def get_strong_areas(
        self, user_id: str, topic: str | None = None, threshold: float = 0.8
    ) -> list[UserProgress]:
        """Concepts with confidence at or above threshold, strongest first."""
        progress = self.get_user_progress(user_id, topic)
        strong = [p for p in progress if p.confidence_score >= threshold]
        strong.sort(key=lambda p: -p.confidence_score)
        return strong

    def needs_reteach(self, user_id: str, topic: str, concept: str) -> bool:
        """True if user has failed repeatedly on this concept."""
        record = self.get_concept_progress(user_id, topic, concept)
        if not record:
            return False
        return record.consecutive_wrong >= RETEACH_FAILURE_THRESHOLD

    def get_last_mistake_type(
        self, user_id: str, topic: str, concept: str
    ) -> str | None:
        """Most recent mistake_type for a concept from answer_log."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT mistake_type FROM answer_log
                WHERE user_id = ? AND topic = ? AND concept = ?
                  AND mistake_type IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id, topic, concept),
            ).fetchone()
        return row["mistake_type"] if row else None

    def count_recent_errors_by_type(
        self,
        user_id: str,
        topic: str,
        concept: str,
        error_type: str,
        limit: int = 5,
    ) -> int:
        """Count recent attempts with a specific error type."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS cnt FROM (
                    SELECT mistake_type FROM answer_log
                    WHERE user_id = ? AND topic = ? AND concept = ?
                      AND correct = 0
                    ORDER BY created_at DESC
                    LIMIT ?
                ) WHERE mistake_type = ?
                """,
                (user_id, topic, concept, limit, error_type),
            ).fetchone()
        return int(row["cnt"]) if row else 0

    def get_answer_history(
        self, user_id: str, limit: int = 50
    ) -> list[dict]:
        """Recent answer log entries for debugging or analytics."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM answer_log
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_confidence_timeline(
        self, user_id: str, topic: str, limit: int = 200
    ) -> list[dict]:
        """
        Chronological confidence snapshots after each evaluated answer.

        Uses confidence_after when present; otherwise replays smoothed accuracy.
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT concept, correct, created_at, confidence_after
                FROM answer_log
                WHERE user_id = ? AND topic = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (user_id, topic, limit),
            ).fetchall()

        replay_correct: dict[str, int] = {}
        replay_attempts: dict[str, int] = {}
        timeline: list[dict] = []

        for row in rows:
            concept = row["concept"]
            replay_attempts[concept] = replay_attempts.get(concept, 0) + 1
            if row["correct"]:
                replay_correct[concept] = replay_correct.get(concept, 0) + 1

            if row["confidence_after"] is not None:
                confidence = float(row["confidence_after"])
            else:
                confidence = self.compute_confidence(
                    replay_attempts[concept],
                    replay_correct.get(concept, 0),
                )

            timeline.append(
                {
                    "concept": concept,
                    "confidence": confidence,
                    "correct": bool(row["correct"]),
                    "created_at": row["created_at"],
                }
            )
        return timeline
