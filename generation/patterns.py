"""Track repeated mistake patterns per user and concept."""

from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from config import EVALUATION_LOGS_DB_PATH


@dataclass
class MistakePattern:
    """Aggregated error pattern for a user on one concept."""

    user_id: str
    concept: str
    total_errors: int
    dominant_error_type: str
    error_counts: dict[str, int]


class MistakePatternTracker:
    """Reads evaluation logs to surface persistent mistake types."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or EVALUATION_LOGS_DB_PATH

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_pattern(self, user_id: str, concept: str) -> MistakePattern | None:
        if not self.db_path.exists():
            return None
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT error_type FROM evaluation_log
                WHERE user_id = ? AND concept = ? AND is_correct = 0
                ORDER BY created_at DESC
                LIMIT 20
                """,
                (user_id, concept),
            ).fetchall()
        if not rows:
            return None
        counts = Counter(r["error_type"] for r in rows if r["error_type"] != "none")
        if not counts:
            return None
        dominant, _ = counts.most_common(1)[0]
        return MistakePattern(
            user_id=user_id,
            concept=concept,
            total_errors=sum(counts.values()),
            dominant_error_type=dominant,
            error_counts=dict(counts),
        )

    def should_reteach_for_concept(self, user_id: str, concept: str, threshold: int = 3) -> bool:
        """True if conceptual errors dominate recent attempts."""
        pattern = self.get_pattern(user_id, concept)
        if not pattern or pattern.total_errors < threshold:
            return False
        conceptual = pattern.error_counts.get("conceptual_error", 0)
        return conceptual >= threshold and pattern.dominant_error_type == "conceptual_error"

    def should_practice_calculation(self, user_id: str, concept: str) -> bool:
        """True if calculation errors dominate — more drill, less reteach."""
        pattern = self.get_pattern(user_id, concept)
        if not pattern:
            return False
        return pattern.dominant_error_type == "calculation_error"
