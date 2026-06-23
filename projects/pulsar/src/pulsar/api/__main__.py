"""Run the Pulsar API server: ``python -m pulsar.api``.

Serves the app (and, via its lifespan, the scheduler) on localhost:8000. Host and
port are intentionally fixed for now; move them to settings when deployment needs
it. Interactive docs at ``/docs``.
"""

from __future__ import annotations

import uvicorn

HOST = "127.0.0.1"
PORT = 8000


def main() -> int:
    """Start the ASGI server (factory mode, so the app is built per worker)."""
    uvicorn.run("pulsar.api.app:create_app", factory=True, host=HOST, port=PORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
