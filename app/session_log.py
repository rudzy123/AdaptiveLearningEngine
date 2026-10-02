"""Session observability logging."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import ENGINE_DATA_DIR

logger = logging.getLogger(__name__)

SESSION_DB = ENGINE_DATA_DIR / "session_logs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS session_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    concept TEXT,
    event_type TEXT NOT NULL,
    payload_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_session_user ON session_events(user_id, created_at);
"""


class SessionLogger:
    """Log answers, scores, and time spent for observability."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or SESSION_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def log(
        self,
        user_id: str,
        topic: str,
        event_type: str,
        *,
        concept: str = "",
        payload: dict | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO session_events
                (user_id, topic, concept, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    topic,
                    concept,
                    event_type,
                    json.dumps(payload or {}),
                    now,
                ),
            )
            conn.commit()
        logger.debug("session_event %s %s %s", user_id, event_type, concept)
