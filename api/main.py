"""
Legacy import path — forwards to app.main.

Prefer: uvicorn app.main:app --reload --port 8000
"""

from app.main import app  # noqa: F401
