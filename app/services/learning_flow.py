"""
Deprecated facade — delegates to LearningSession.

Kept for backward compatibility with older imports and scripts.
"""

from __future__ import annotations

from app.services.learning_session import LearningSession, get_session

# Re-export exception name used by legacy code
from app.services.exceptions import ServiceError as LearningFlowError  # noqa: F401

_flow = get_session()


def initialize_topic(user_id: str, topic: str, level: str = "beginner") -> dict:
    return _flow.start_topic(user_id, topic, level)


def generate_lesson(user_id: str) -> dict:
    return _flow.get_lesson(user_id)


def generate_problem(user_id: str) -> dict:
    return _flow.get_problem(user_id)


def evaluate_and_update(user_id: str, answer: str) -> dict:
    return _flow.submit_answer(user_id, answer)


def decide_next_action(user_id: str) -> dict:
    return _flow.decide_next_step(user_id)


def get_progress(user_id: str) -> dict:
    return _flow.get_progress(user_id)
