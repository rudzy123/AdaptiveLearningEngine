"""Input validation for API/service layer."""

from __future__ import annotations

import re

from app.services.exceptions import ServiceError

USER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]{1,64}$")
VALID_LEVELS = frozenset({"beginner", "intermediate", "advanced"})


def validate_user_id(user_id: str) -> str:
    """Require non-empty, bounded user id."""
    uid = (user_id or "").strip()
    if not uid:
        raise ServiceError("user_id is required", 400)
    if not USER_ID_PATTERN.match(uid):
        raise ServiceError("user_id contains invalid characters", 400)
    return uid


def validate_topic(topic: str) -> str:
    """Require non-empty topic string."""
    t = (topic or "").strip()
    if not t:
        raise ServiceError("topic is required", 400)
    if len(t) > 120:
        raise ServiceError("topic is too long", 400)
    return t


def validate_level(level: str) -> str:
    """Normalize learner level."""
    lv = (level or "beginner").strip().lower()
    if lv not in VALID_LEVELS:
        raise ServiceError(
            f"level must be one of: {', '.join(sorted(VALID_LEVELS))}", 400
        )
    return lv


def validate_answer(answer: str) -> str:
    """Require non-empty answer."""
    a = (answer or "").strip()
    if not a:
        raise ServiceError("answer cannot be empty", 400)
    if len(a) > 8000:
        raise ServiceError("answer is too long", 400)
    return a
