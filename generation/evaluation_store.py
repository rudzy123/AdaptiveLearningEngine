"""Persist deep evaluation results to SQLite."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from config import EVALUATION_LOGS_DB_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS evaluation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    topic TEXT,
    concept TEXT NOT NULL,
    question TEXT,
    user_answer TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    is_correct INTEGER NOT NULL,
    score REAL NOT NULL,
    error_type TEXT NOT NULL,
    feedback TEXT,
    hint TEXT,
    confidence_adjustment REAL,
    layer_scores_json TEXT,
    hints_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_eval_user_concept
    ON evaluation_log(user_id, concept);

CREATE INDEX IF NOT EXISTS idx_eval_error_type
    ON evaluation_log(error_type);
"""


class EvaluationStore:
    """Log every deep evaluation for analytics and pattern tracking."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or EVALUATION_LOGS_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()

    def log_evaluation(self, record: dict) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO evaluation_log
                (user_id, topic, concept, question, user_answer, correct_answer,
                 difficulty, is_correct, score, error_type, feedback, hint,
                 confidence_adjustment, layer_scores_json, hints_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["user_id"],
                    record.get("topic", ""),
                    record["concept"],
                    record.get("question", ""),
                    record["user_answer"],
                    record["correct_answer"],
                    record.get("difficulty_level", "beginner"),
                    1 if record["is_correct"] else 0,
                    record["score"],
                    record["error_type"],
                    record.get("feedback", ""),
                    record.get("hint", ""),
                    record.get("confidence_adjustment", 0.0),
                    json.dumps(record.get("layer_scores", {})),
                    json.dumps(record.get("hints", [])),
                    record.get("created_at", ""),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)
