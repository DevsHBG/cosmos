"""SAP HANA connection helpers (hdbcli)."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any

from pulsar.config.settings import get_hana_settings


@contextlib.contextmanager
def hana_connection() -> Iterator[Any]:
    """Open a SAP HANA connection as a context manager.

    The hdbcli connection object does not implement the context-manager
    protocol itself, so this wrapper guarantees the connection is closed.

    Yields:
        An open hdbcli connection.
    """
    from hdbcli import dbapi

    s = get_hana_settings()
    conn = dbapi.connect(address=s.host, port=s.port, user=s.user, password=s.password)
    try:
        yield conn
    finally:
        with contextlib.suppress(Exception):
            conn.close()
