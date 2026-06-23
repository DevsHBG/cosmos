"""RFC 9457 Problem Details for the Pulsar API.

Errors are returned as ``application/problem+json`` (RFC 9457) instead of FastAPI's
default ``{"detail": ...}`` body. Endpoints raise :class:`ProblemException` for a
typed problem; the registered handlers also convert framework errors (unmatched
routes, method-not-allowed, request validation) to the same shape. Every problem
carries the request's ``correlation_id`` as an extension member, so an error links
to its log row (see ``docs/arquitectura-restful.md`` §9).
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse, Response

from pulsar.logger.context import current_correlation_id

#: Base URI for Pulsar-specific problem ``type`` identifiers.
_TYPE_BASE = "https://pulsar/errors/"


class Problem(BaseModel):
    """An RFC 9457 problem detail (media type ``application/problem+json``)."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    correlation_id: str | None = None  # extension member: links the error to its log


class ProblemResponse(JSONResponse):
    """A JSON response tagged with the ``application/problem+json`` media type."""

    media_type = "application/problem+json"


class ProblemException(Exception):  # noqa: N818 - it *is* a problem, not an "Error"
    """Raise from an endpoint to return a typed RFC 9457 problem.

    Args:
        status: HTTP status code (mirrored into the body's ``status``).
        title: Stable, human-readable summary of the problem type.
        detail: Explanation specific to this occurrence.
        type_slug: Appended to :data:`_TYPE_BASE` to form the ``type`` URI;
            ``None`` leaves it as ``about:blank``.
    """

    def __init__(
        self,
        status: int,
        title: str,
        *,
        detail: str | None = None,
        type_slug: str | None = None,
    ) -> None:
        self.status = status
        self.title = title
        self.detail = detail
        self.type = f"{_TYPE_BASE}{type_slug}" if type_slug else "about:blank"
        super().__init__(detail or title)


def _problem_response(
    request: Request,
    *,
    status: int,
    title: str,
    detail: str | None = None,
    type_: str = "about:blank",
    **extensions: Any,
) -> ProblemResponse:
    """Build an ``application/problem+json`` response for the current request."""
    problem = Problem(
        type=type_,
        title=title,
        status=status,
        detail=detail,
        instance=request.url.path,
        correlation_id=current_correlation_id(),
    )
    body = problem.model_dump()
    body.update(extensions)  # extension members (e.g. validation errors)
    return ProblemResponse(status_code=status, content=body)


def register_problem_handlers(app: FastAPI) -> None:
    """Install the handlers that render every error as RFC 9457 problem+json."""

    @app.exception_handler(ProblemException)
    async def _on_problem(request: Request, exc: ProblemException) -> Response:
        return _problem_response(
            request, status=exc.status, title=exc.title, detail=exc.detail, type_=exc.type
        )

    @app.exception_handler(StarletteHTTPException)
    async def _on_http(request: Request, exc: StarletteHTTPException) -> Response:
        title = HTTPStatus(exc.status_code).phrase
        # Drop a default detail that just repeats the title (e.g. "Not Found").
        detail = exc.detail if isinstance(exc.detail, str) and exc.detail != title else None
        response = _problem_response(request, status=exc.status_code, title=title, detail=detail)
        if exc.headers:  # preserve framework headers, e.g. ``Allow`` on a 405
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(RequestValidationError)
    async def _on_validation(request: Request, exc: RequestValidationError) -> Response:
        return _problem_response(
            request,
            status=422,
            title="Unprocessable Content",
            detail="One or more request parameters are invalid.",
            type_=f"{_TYPE_BASE}validation",
            errors=jsonable_encoder(exc.errors()),
        )
