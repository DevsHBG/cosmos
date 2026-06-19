"""Lakehouse storage: a DuckLake lake over a SQLite catalog + Parquet files."""

from __future__ import annotations

from pulsar.storage.lake import open_lake

__all__ = ["open_lake"]
