#!/usr/bin/env python3
"""
FastAPI application — Adaptive Learning Engine (production API).

Run:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api.envelope import error  # noqa: E402
from app.api.routes import router  # noqa: E402
from app.services.exceptions import ServiceError  # noqa: E402
from pipeline.logging_setup import setup_logging  # noqa: E402

setup_logging("adaptive_learning_api")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Adaptive Learning Engine API",
    version="3.0.0",
    description="Production REST API — lessons, problems, evaluation, progression",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ServiceError)
async def service_error_handler(_request: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.code,
        content=error(exc.message, exc.code),
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error("Validation failed: " + str(exc.errors()), 422),
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content=error("Internal server error", 500),
    )


app.include_router(router, tags=["learning"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def root() -> dict:
    return {
        "service": "Adaptive Learning Engine API",
        "version": "3.0.0",
        "docs": "/docs",
        "endpoints": {
            "POST /start_topic": "Initialize topic",
            "GET /lesson/{user_id}": "Lesson + RAG chunks",
            "GET /problem/{user_id}": "Practice problem",
            "POST /submit_answer": "Evaluate answer",
            "POST /next_step/{user_id}": "Progression",
            "GET /progress/{user_id}": "Confidence scores",
        },
        "response_format": {
            "success": {"status": "success", "data": "{...}"},
            "error": {"status": "error", "error": {"message": "...", "code": 400}},
        },
    }
