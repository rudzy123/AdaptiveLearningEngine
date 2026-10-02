"""HTTP API (FastAPI) over the Tutor.

Every response uses one envelope:
    success: {"status": "success", "data": ...}
    error:   {"status": "error", "error": {"message": str, "code": str}}

Stack traces are logged server-side and never sent to clients.

Run:  python -m ale serve        (or: uvicorn ale.interfaces.api:create_app --factory)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Path as PathParam, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from ale import __version__
from ale.engine.errors import TutorError
from ale.engine.tutor import MAX_ANSWER_CHARS, USER_ID_RE, Tutor

logger = logging.getLogger("ale.api")

USER_ID = PathParam(..., pattern=USER_ID_RE.pattern, description="1-64 chars: letters, digits, _ . -")

_STATUS_CODES = {
    400: "bad_request", 404: "not_found", 405: "method_not_allowed", 409: "conflict",
    415: "unsupported_media_type", 422: "validation_error",
}


def ok(data: Any, status: int = 200) -> JSONResponse:
    return JSONResponse({"status": "success", "data": data}, status_code=status)


def fail(message: str, code: str, status: int) -> JSONResponse:
    return JSONResponse({"status": "error", "error": {"message": message, "code": code}}, status_code=status)


class StartTopic(BaseModel):
    user_id: str = Field(..., pattern=USER_ID_RE.pattern, description="Learner id")
    topic: str = Field(..., min_length=1, max_length=120)
    restart: bool = False


class SubmitAnswer(BaseModel):
    problem_id: str = Field(..., min_length=1, max_length=64)
    answer: str = Field(..., min_length=1, max_length=MAX_ANSWER_CHARS)
    reasoning: str = Field("", max_length=MAX_ANSWER_CHARS)


def create_app(db_path: str | Path | None = None) -> FastAPI:
    tutor = Tutor(db_path)
    app = FastAPI(
        title="Adaptive Learning Engine",
        version=__version__,
        description="A local adaptive tutor: local RAG, 5-layer evaluation, confidence-based progression, "
        "persistent learner state. No external APIs.",
    )
    app.state.tutor = tutor

    # ---- error handling -------------------------------------------------
    @app.exception_handler(TutorError)
    async def _tutor_error(_: Request, exc: TutorError) -> JSONResponse:
        return fail(exc.message, exc.code, exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", ()) if p not in ("body", "path", "query"))
        message = f"{loc}: {first.get('msg', 'invalid request')}" if loc else first.get("msg", "invalid request")
        return fail(message, "validation_error", 422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        message = "Resource not found" if exc.status_code == 404 else str(exc.detail)
        return fail(message, code, exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return fail("Internal server error", "internal_error", 500)

    # ---- routes ---------------------------------------------------------
    @app.get("/health")
    def health() -> JSONResponse:
        return ok(
            {
                "service": "adaptive-learning-engine",
                "version": __version__,
                "chunks_indexed": tutor.store.chunk_count(),
                "external_apis": False,
            }
        )

    @app.get("/api/topics")
    def topics() -> JSONResponse:
        return ok({"topics": tutor.topics()})

    @app.get("/api/search")
    def search(q: str = Query(..., min_length=1, max_length=300), k: int = Query(4, ge=1, le=10)) -> JSONResponse:
        return ok({"query": q, "results": tutor.search(q, k)})

    @app.post("/api/sessions")
    def start_topic(body: StartTopic) -> JSONResponse:
        return ok(tutor.start_topic(body.user_id, body.topic, body.restart), 201)

    @app.get("/api/users/{user_id}/session")
    def session(user_id: str = USER_ID) -> JSONResponse:
        return ok(tutor.state(user_id))

    @app.get("/api/users/{user_id}/lesson")
    def lesson(user_id: str = USER_ID) -> JSONResponse:
        return ok(tutor.get_lesson(user_id))

    @app.get("/api/users/{user_id}/problem")
    def problem(user_id: str = USER_ID) -> JSONResponse:
        return ok(tutor.get_problem(user_id))

    @app.post("/api/users/{user_id}/answers")
    def answer(body: SubmitAnswer, user_id: str = USER_ID) -> JSONResponse:
        return ok(tutor.submit_answer(user_id, body.problem_id, body.answer, body.reasoning))

    @app.get("/api/users/{user_id}/progress")
    def progress(user_id: str = USER_ID) -> JSONResponse:
        return ok(tutor.progress(user_id))

    return app
