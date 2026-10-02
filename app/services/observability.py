"""Structured logging to file logger + SQLite api_logs."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Generator

from data.api_log_repository import ApiLogRepository

logger = logging.getLogger("adaptive_learning.api")


class RequestObserver:
    """Context manager for endpoint latency and persistence."""

    def __init__(self, repo: ApiLogRepository | None = None) -> None:
        self._repo = repo or ApiLogRepository()

    @contextmanager
    def track(
        self,
        endpoint: str,
        *,
        user_id: str | None = None,
        concept: str | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """
        Yield a mutable context dict; on exit log latency and persist row.

        Attach score/error_type via ctx["score"], ctx["error_type"] before exit.
        """
        ctx: dict[str, Any] = {}
        start = time.perf_counter()
        status = "success"
        message = ""
        try:
            yield ctx
        except Exception as exc:
            status = "error"
            message = str(exc)
            raise
        finally:
            status = str(ctx.get("status", status))
            message = str(ctx.get("message", message or ""))
            concept_value = str(ctx.get("concept", concept or "-"))
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "endpoint=%s user=%s concept=%s latency_ms=%.1f status=%s score=%s error_type=%s",
                endpoint,
                user_id or "-",
                concept_value,
                elapsed_ms,
                status,
                ctx.get("score"),
                ctx.get("error_type"),
            )
            self._repo.write(
                endpoint=endpoint,
                status=status,
                user_id=user_id,
                concept=concept_value,
                latency_ms=elapsed_ms,
                score=ctx.get("score"),
                error_type=ctx.get("error_type"),
                message=message or ctx.get("message"),
                payload=ctx.get("payload"),
            )
