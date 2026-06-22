"""Modeled warehouse over the lake: movements, masters and facts.

Organized by data kind. Today: :mod:`pulsar.model.movements` (the OINM journal).
Future masters/facts live as sibling packages, each one its own table in the
lake, namespaced by a domain schema (e.g. ``inventory.movements``).
"""

from __future__ import annotations
