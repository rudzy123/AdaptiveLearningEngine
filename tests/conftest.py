"""Pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def tmp_session_db(tmp_path, monkeypatch):
    """Isolated session + log DBs per test."""
    session_db = tmp_path / "session_state.db"
    log_db = tmp_path / "logs.db"
    progress_db = tmp_path / "user_progress.db"

    monkeypatch.setattr("config.SESSION_STATE_DB_PATH", session_db)
    monkeypatch.setattr("config.API_LOGS_DB_PATH", log_db)
    monkeypatch.setattr("config.USER_PROGRESS_DB_PATH", progress_db)

    from data.session_repository import SessionRepository
    from app.services.learning_session import LearningSession

    return LearningSession(sessions=SessionRepository(session_db))
