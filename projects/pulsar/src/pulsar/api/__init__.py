"""Pulsar HTTP API (FastAPI): hosts the scheduler and exposes job control."""

from __future__ import annotations

from pulsar.api.app import create_app

__all__ = ["create_app"]
