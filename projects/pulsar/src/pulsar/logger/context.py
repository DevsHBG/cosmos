"""Correlation-id propagation via a context variable.

A single ``correlation_id`` ties together every log emitted during one logical
operation (an HTTP request, a job run) so the unified query can follow an action
end to end. Any ``log.emit(...)`` inside a bound scope inherits the id without
threading it through call signatures.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def new_correlation_id() -> str:
    """Return a fresh, unique correlation id."""
    return uuid.uuid4().hex


def current_correlation_id() -> str | None:
    """Return the correlation id bound to the current context (or ``None``)."""
    return _correlation_id.get()


@contextmanager
def correlation_scope(correlation_id: str | None = None) -> Iterator[str]:
    """Bind a correlation id for the duration of the ``with`` block.

    Args:
        correlation_id: Id to bind; a fresh one is generated when ``None``.

    Yields:
        The correlation id bound for the scope.
    """
    cid = correlation_id or new_correlation_id()
    token = _correlation_id.set(cid)
    try:
        yield cid
    finally:
        _correlation_id.reset(token)
