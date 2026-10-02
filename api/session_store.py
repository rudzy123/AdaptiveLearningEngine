"""In-memory session store for API requests."""

from __future__ import annotations

import uuid
from threading import Lock

from app.panel_controller import LearningPanelState

_lock = Lock()
_sessions: dict[str, LearningPanelState] = {}


def create_session(state: LearningPanelState) -> str:
    session_id = str(uuid.uuid4())
    with _lock:
        _sessions[session_id] = state
    return session_id


def get_session(session_id: str) -> LearningPanelState | None:
    with _lock:
        return _sessions.get(session_id)


def update_session(session_id: str, state: LearningPanelState) -> None:
    with _lock:
        _sessions[session_id] = state


def delete_session(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)
