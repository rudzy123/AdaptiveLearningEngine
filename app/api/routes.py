"""HTTP routes — no business logic; delegate to LearningSession only."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.envelope import error, success
from app.api.schemas import AnswerRequest, TopicRequest, UserIdBody
from app.services.exceptions import ServiceError
from app.services.learning_session import get_session
from app.services.observability import RequestObserver

router = APIRouter()
_observer = RequestObserver()
_session = get_session()


def _ok(data: dict, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=success(data))


def _err(exc: ServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.code,
        content=error(exc.message, exc.code),
    )


@router.post("/start_topic")
def start_topic(body: TopicRequest, request: Request) -> JSONResponse:
    with _observer.track("/start_topic", user_id=body.user_id) as ctx:
        try:
            data = _session.start_topic(body.user_id, body.topic, body.level)
            ctx["payload"] = {"topic": data.get("topic")}
            return _ok(data, 201)
        except ServiceError as exc:
            ctx["status"] = "error"
            ctx["message"] = exc.message
            return _err(exc)


@router.get("/lesson/{user_id}")
def get_lesson(user_id: str, request: Request) -> JSONResponse:
    with _observer.track("/lesson/{user_id}", user_id=user_id) as ctx:
        try:
            data = _session.get_lesson(user_id)
            ctx["concept"] = data.get("concept")
            return _ok(data)
        except ServiceError as exc:
            ctx["status"] = "error"
            ctx["message"] = exc.message
            return _err(exc)


@router.get("/problem/{user_id}")
def get_problem(user_id: str, request: Request) -> JSONResponse:
    with _observer.track("/problem/{user_id}", user_id=user_id) as ctx:
        try:
            data = _session.get_problem(user_id)
            ctx["concept"] = data.get("concept")
            return _ok(data)
        except ServiceError as exc:
            ctx["status"] = "error"
            ctx["message"] = exc.message
            return _err(exc)


@router.post("/submit_answer")
def submit_answer(body: AnswerRequest, request: Request) -> JSONResponse:
    with _observer.track("/submit_answer", user_id=body.user_id) as ctx:
        try:
            data = _session.submit_answer(body.user_id, body.answer)
            ctx["score"] = data.get("score")
            ctx["error_type"] = data.get("error_type")
            ctx["concept"] = data.get("concept")
            ctx["payload"] = {"next_action": data.get("next_action")}
            return _ok(data)
        except ServiceError as exc:
            ctx["status"] = "error"
            ctx["message"] = exc.message
            return _err(exc)


@router.post("/next_step/{user_id}")
def next_step(user_id: str, request: Request) -> JSONResponse:
    with _observer.track("/next_step/{user_id}", user_id=user_id) as ctx:
        try:
            data = _session.decide_next_step(user_id)
            ctx["concept"] = data.get("next_concept")
            return _ok(data)
        except ServiceError as exc:
            ctx["status"] = "error"
            ctx["message"] = exc.message
            return _err(exc)


@router.get("/progress/{user_id}")
def get_progress(user_id: str, request: Request) -> JSONResponse:
    with _observer.track("/progress/{user_id}", user_id=user_id) as ctx:
        try:
            return _ok(_session.get_progress(user_id))
        except ServiceError as exc:
            ctx["status"] = "error"
            ctx["message"] = exc.message
            return _err(exc)


# Legacy POST aliases (backward compatibility)
@router.post("/get_lesson")
def get_lesson_legacy(body: UserIdBody, request: Request) -> JSONResponse:
    return get_lesson(body.user_id, request)


@router.post("/get_problem")
def get_problem_legacy(body: UserIdBody, request: Request) -> JSONResponse:
    return get_problem(body.user_id, request)


@router.post("/next_step")
def next_step_legacy(body: UserIdBody, request: Request) -> JSONResponse:
    return next_step(body.user_id, request)
