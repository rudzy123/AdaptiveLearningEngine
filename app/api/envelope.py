"""Standard API response envelopes."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    message: str
    code: int = 400


class ErrorEnvelope(BaseModel):
    status: str = "error"
    error: ErrorDetail


class SuccessEnvelope(BaseModel, Generic[T]):
    status: str = "success"
    data: T


def success(data: Any) -> dict[str, Any]:
    """Build success JSON body."""
    return {"status": "success", "data": data}


def error(message: str, code: int = 400) -> dict[str, Any]:
    """Build error JSON body."""
    return {
        "status": "error",
        "error": {"message": message, "code": code},
    }
