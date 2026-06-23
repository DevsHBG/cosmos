"""HTTP capture: a middleware that logs every request as an ``ApiLog``.

Records metadata always (method, path, status, duration, correlation id) and, only
on failure (status ≥ 400), a capped copy of the response body. Each request runs in
a fresh correlation scope (honouring an inbound ``X-Correlation-ID`` header), so any
log emitted while handling the request — including a job it triggers — shares the id.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from pulsar.logger import ApiLog, log
from pulsar.logger.config import get_logger_settings
from pulsar.logger.context import correlation_scope, new_correlation_id

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request


class LoggingMiddleware(BaseHTTPMiddleware):
    """Time each request, bind a correlation id, and emit an ``ApiLog``."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = datetime.now(UTC)
        cid = request.headers.get("x-correlation-id") or new_correlation_id()
        with correlation_scope(cid):
            response = await call_next(request)
        finished = datetime.now(UTC)

        captured: str | None = None
        if response.status_code >= 400:
            captured, response = await self._capture_body(response)

        self._emit(request, response.status_code, started, finished, cid, captured)
        return response

    @staticmethod
    async def _capture_body(response: Response) -> tuple[str | None, Response]:
        """Consume a (failed) streaming response and rebuild it, returning the body."""
        cap = get_logger_settings().response_cap_bytes
        body_iterator = getattr(response, "body_iterator", None)  # only on streaming responses
        if body_iterator is None:
            return None, response
        try:
            chunks = [chunk async for chunk in body_iterator]
        except Exception:  # best-effort: never break serving the request
            return None, response
        body = b"".join(
            bytes(chunk) if isinstance(chunk, memoryview | bytearray) else chunk for chunk in chunks
        )
        rebuilt = Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
        return body[:cap].decode("utf-8", "replace"), rebuilt

    @staticmethod
    def _emit(
        request: Request,
        status_code: int,
        started: datetime,
        finished: datetime,
        cid: str,
        captured: str | None,
    ) -> None:
        failed = status_code >= 400
        log.emit(
            ApiLog(
                ts=finished,
                level="error" if status_code >= 500 else ("warn" if failed else "info"),
                correlation_id=cid,
                source="http",
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                status="failed" if failed else "ok",
                started_at=started,
                finished_at=finished,
                duration_ms=int((finished - started).total_seconds() * 1000),
                detail=captured,
            )
        )
